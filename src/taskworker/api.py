from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from taskworker.config import Settings
from taskworker.database import Database
from taskworker.models import LedgerRecord, RunResponse, TaskRequest, WorkspaceSnapshot
from taskworker.planner import ResilientPlanner
from taskworker.tools import InternalLedgerTool, InvoiceExtractorTool, MailboxTool
from taskworker.worker import TaskWorker


def build_worker(settings: Settings) -> TaskWorker:
    database = Database(settings.database_path)
    database.initialize()
    return TaskWorker(
        database=database,
        planner=ResilientPlanner(settings),
        mailbox=MailboxTool(database),
        extractor=InvoiceExtractorTool(),
        ledger=InternalLedgerTool(database, fail_first_write=settings.demo_transient_failure),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings.from_environment()
    worker = build_worker(active_settings)
    static_dir = Path(__file__).resolve().parents[2] / "public"

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    app = FastAPI(title="Autonomous Task Worker", version="0.1.0", lifespan=lifespan)
    app.state.worker = worker
    app.state.database = worker.database
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "planner_mode": active_settings.planner_provider}

    @app.post("/api/tasks", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
    def create_task(request: TaskRequest) -> RunResponse:
        return worker.run(request.task)

    @app.get("/api/runs/{run_id}", response_model=RunResponse)
    def get_run(run_id: str) -> RunResponse:
        run = worker.database.get_run(run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
        return run

    @app.get("/api/ledger", response_model=list[LedgerRecord])
    def get_ledger() -> list[LedgerRecord]:
        return worker.database.list_ledger()

    @app.get("/api/workspace", response_model=WorkspaceSnapshot)
    def get_workspace() -> WorkspaceSnapshot:
        return WorkspaceSnapshot(
            suppliers=worker.database.supplier_names(),
            inbox=worker.database.list_invoices(),
            ledger=worker.database.list_ledger(),
            recent_runs=worker.database.list_recent_runs(),
        )

    @app.post("/api/demo/reset", status_code=status.HTTP_200_OK)
    def reset_demo() -> dict[str, str]:
        worker.database.reset_demo()
        return {
            "status": "reset",
            "note": "Demo-only endpoint: local run and ledger history were cleared.",
        }

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("taskworker.api:app", host="127.0.0.1", port=8000, reload=True)
