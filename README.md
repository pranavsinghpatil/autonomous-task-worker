# Autonomous Task Worker

Autonomous Task Worker is a Python-first prototype for completing one business workflow in a simulated company environment: invoice intake. A user describes an outcome, a planner proposes a constrained plan, and the worker calls explicit tools to find the latest seeded invoice, extract its fields, write a local ledger record, and verify that record independently.

The dashboard makes the plan, tool activity, retry, evidence, and final state visible. A run is marked complete only after the ledger's persisted invoice number, amount, and due date match the extracted source record.

## Scope and safety

This is a local demonstration, not a production agent. The mailbox and ledger are seeded simulation data stored in SQLite. The application does not connect to real email, accounting software, payment systems, or browser sessions. It does not perform browser automation or send money.

Payment or transfer requests stop at `awaiting_approval` before tools run. A missing or unknown supplier stops at `awaiting_clarification`. The planner may select only the four invoice-workflow actions supported by the worker. Invalid planner output is rejected and handled through the configured fallback; it is never executed as a tool call. A predictable transient ledger error demonstrates one bounded retry per run.

## Requirements and setup

- Python 3.12
- [`uv`](https://docs.astral.sh/uv/) for the project environment and locked dependencies

From the repository root:

```powershell
uv python install 3.12 --install-dir .python --cache-dir .uv-cache --no-bin --no-registry
uv sync --locked --cache-dir .uv-cache --python .python/cpython-3.12-windows-x86_64-none/python.exe
Copy-Item .env.example .env
uv run --cache-dir .uv-cache uvicorn taskworker.api:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). If the application entry point differs, use the `uvicorn` command in the project configuration or update this command to match it.

No API key is required for local operation: the deterministic planner supports repeatable offline demos. To use a hosted planner, put the appropriate key in `.env` (never commit that file) and choose a provider as described below.

## Planner configuration

`PLANNER_PROVIDER` accepts `auto`, `groq`, `gemini`, or `offline`.

- `auto` tries Groq first when `GROQ_API_KEY` is present, then Gemini when `GEMINI_API_KEY` is present, then the deterministic offline planner.
- `groq` selects Groq as the preferred provider; on an unavailable provider or failed/invalid response, the worker may fall back to configured Gemini and then offline planning.
- `gemini` prefers Gemini, then uses offline planning if Gemini is unavailable or fails.
- `offline` always uses the deterministic planner.

The run record and dashboard identify the provider that actually produced the plan; offline planning is explicitly labeled and must not be represented as an LLM result. Model names can be overridden with `GROQ_MODEL` and `GEMINI_MODEL`. See `.env.example` for the accepted variables and defaults.

Hosted provider calls send the user's task text to that provider. Do not use private business data or real credentials in this prototype.

## Workflow and architecture

The prototype seeds invoices for Acme Supplies, Northwind Logistics, and Contoso Cloud. Its supported path is:

1. Classify the request and apply approval/clarification gates.
2. Produce and validate a structured, four-action invoice plan.
3. Find the supplier's latest simulated invoice and extract its fields.
4. Write an idempotent ledger entry, retrying one explicitly retryable transient error at most once.
5. Read the ledger independently and compare invoice number, amount, and due date.
6. Persist the run, ordered events, and evidence for review in the dashboard.

See [docs/architecture.md](docs/architecture.md) for the component diagram, data flow, and failure behavior.

## Running checks

```powershell
uv run --cache-dir .uv-cache pytest
uv run --cache-dir .uv-cache ruff check .
uv run --cache-dir .uv-cache pyright
```

These checks cover planner routing and validation, deterministic fallback, safety stops, invoice selection, retry bounds, idempotency, verification, and the HTTP API.

## API

- `POST /api/tasks` — submit `{ "task": "..." }` and receive the resulting run.
- `GET /api/runs/{run_id}` — retrieve a run, its plan, events, and evidence.
- `GET /api/ledger` — inspect persisted ledger entries.
- `POST /api/demo/reset` — a clearly demo-only reset action for local run and ledger state; never expose it in a shared deployment.

The exact response models are defined in the application and should be treated as the source of truth.

## Demo

Follow [docs/demo-script.md](docs/demo-script.md) for a 90–120 second recording. It covers a successful invoice run, the visible transient retry and independent verification, and the approval and clarification safety stops. A configured Groq or Gemini provider may be shown; otherwise the script labels the deterministic offline planner accurately.

## Limitations and next steps

The seeded mailbox, field extraction, and ledger are local adapters. Provider planning is limited to a validated invoice-task schema and the seeded suppliers. The approval state demonstrates a stop before sensitive work; it is not a human approval queue. Local SQLite and a local dashboard are suitable for this prototype only. Production use would require real integration adapters, authentication and authorization, secrets management, durable task execution, concurrency controls, stronger policy enforcement, and operational monitoring.
