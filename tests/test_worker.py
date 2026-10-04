from __future__ import annotations

from taskworker.api import build_worker
from taskworker.database import Database
from taskworker.models import InvoicePlan, PlannerResult, RunStatus
from taskworker.planner import OfflinePlanner, Planner, default_actions
from taskworker.tools import InternalLedgerTool, InvoiceExtractorTool, MailboxTool
from taskworker.worker import TaskWorker


def test_successful_run_retries_once_and_verifies(settings) -> None:
    worker = build_worker(settings)
    run = worker.run(
        "Find the latest invoice from Acme Supplies and enter it into the internal ledger."
    )
    assert run.status is RunStatus.COMPLETED
    assert run.result is not None
    assert run.result.invoice_number == "ACME-2026-0918"
    assert [event.type for event in run.events].count("retry") == 1
    assert [event.type for event in run.events].count("failure") == 1
    assert run.events[-1].type == "verified"


def test_repeated_task_is_idempotent(settings) -> None:
    worker = build_worker(settings)
    first = worker.run("Process the latest invoice from Northwind Logistics.")
    second = worker.run("Process the latest invoice from Northwind Logistics.")
    assert first.status is RunStatus.COMPLETED
    assert second.status is RunStatus.COMPLETED
    assert second.result is not None and second.result.already_existed
    assert len(worker.database.list_ledger()) == 1


def test_payment_stops_before_tools(settings) -> None:
    worker = build_worker(settings)
    run = worker.run("Pay the latest invoice from Acme Supplies by bank transfer.")
    assert run.status is RunStatus.AWAITING_APPROVAL
    assert [event.type for event in run.events] == ["safety"]
    assert worker.database.list_ledger() == []


def test_missing_supplier_stops_before_tools(settings) -> None:
    worker = build_worker(settings)
    run = worker.run("Find the latest invoice and put it in the internal system.")
    assert run.status is RunStatus.AWAITING_CLARIFICATION
    assert [event.type for event in run.events] == ["clarification"]
    assert worker.database.list_ledger() == []


def test_live_planner_cannot_invent_a_supplier_for_an_ambiguous_task(settings) -> None:
    class InventedSupplierPlanner(Planner):
        def plan(self, task: str, suppliers: list[str]) -> PlannerResult:
            return PlannerResult(
                provider="test",
                plan=InvoicePlan(
                    company="Acme Supplies",
                    actions=default_actions(),
                    rationale="This deliberately simulates an unsafe model inference.",
                ),
            )

    database = Database(settings.database_path)
    database.initialize()
    worker = TaskWorker(
        database,
        InventedSupplierPlanner(),
        MailboxTool(database),
        InvoiceExtractorTool(),
        InternalLedgerTool(database, fail_first_write=False),
    )
    run = worker.run("Find the latest invoice and enter it into the internal ledger.")
    assert run.status is RunStatus.AWAITING_CLARIFICATION
    assert [event.type for event in run.events] == ["clarification"]
    assert database.list_ledger() == []


def test_live_planner_cannot_switch_the_named_supplier(settings) -> None:
    class MismatchedSupplierPlanner(Planner):
        def plan(self, task: str, suppliers: list[str]) -> PlannerResult:
            return PlannerResult(
                provider="test",
                plan=InvoicePlan(
                    company="Contoso Cloud",
                    actions=default_actions(),
                    rationale="This deliberately simulates an unsafe model selection.",
                ),
            )

    database = Database(settings.database_path)
    database.initialize()
    worker = TaskWorker(
        database,
        MismatchedSupplierPlanner(),
        MailboxTool(database),
        InvoiceExtractorTool(),
        InternalLedgerTool(database, fail_first_write=False),
    )
    run = worker.run("Process the latest invoice from Acme Supplies.")
    assert run.status is RunStatus.AWAITING_CLARIFICATION
    assert [event.type for event in run.events] == ["clarification"]
    assert database.list_ledger() == []


def test_verification_failure_does_not_claim_completion(settings) -> None:
    database = Database(settings.database_path)
    database.initialize()

    class BrokenLedger(InternalLedgerTool):
        def verify(self, invoice_number: str):
            return None

    worker = TaskWorker(
        database,
        OfflinePlanner(),
        MailboxTool(database),
        InvoiceExtractorTool(),
        BrokenLedger(database, fail_first_write=False),
    )
    run = worker.run("Process the latest invoice from Contoso Cloud.")
    assert run.status is RunStatus.FAILED
    assert "Verification failed" in run.summary
