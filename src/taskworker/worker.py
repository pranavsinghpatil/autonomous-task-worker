from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from taskworker.database import Database
from taskworker.models import Event, Evidence, LedgerRecord, RunResponse, RunStatus
from taskworker.planner import Planner, PlannerError
from taskworker.tools import InternalLedgerTool, InvoiceExtractorTool, MailboxTool, ToolError

HIGH_IMPACT_PATTERN = re.compile(r"\b(pay|payment|transfer|send money|wire)\b", re.IGNORECASE)


class TaskWorker:
    def __init__(
        self,
        database: Database,
        planner: Planner,
        mailbox: MailboxTool,
        extractor: InvoiceExtractorTool,
        ledger: InternalLedgerTool,
    ) -> None:
        self.database = database
        self.planner = planner
        self.mailbox = mailbox
        self.extractor = extractor
        self.ledger = ledger

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat()

    def run(self, task: str) -> RunResponse:
        run = RunResponse(
            id=f"run-{uuid4().hex[:8]}",
            task=task,
            status=RunStatus.RUNNING,
            planner_provider="pending",
            started_at=self.now(),
            summary="Planning the requested outcome.",
        )

        def log(event_type: str, message: str, **details: object) -> None:
            run.events.append(
                Event(timestamp=self.now(), type=event_type, message=message, details=details)
            )

        if HIGH_IMPACT_PATTERN.search(task):
            run.status = RunStatus.AWAITING_APPROVAL
            run.planner_provider = "policy"
            run.summary = "This request includes a financial action and requires human approval before execution."
            log("safety", run.summary, policy="financial_action_requires_approval")
            return self._finish(run)

        suppliers = self.database.supplier_names()
        try:
            plan_result = self.planner.plan(task, suppliers)
        except PlannerError as error:
            run.status = RunStatus.AWAITING_CLARIFICATION
            run.planner_provider = "offline"
            run.summary = (
                "I need a recognized supplier before I can safely search the sandbox mailbox."
            )
            log("clarification", run.summary, reason=str(error), suppliers=suppliers)
            return self._finish(run)

        run.plan = plan_result.plan
        run.planner_provider = plan_result.provider
        run.planner_fallback_reason = plan_result.fallback_reason
        log(
            "plan",
            f"Created an allowlisted invoice-intake plan for {run.plan.company}.",
            provider=run.planner_provider,
            fallback_reason=run.planner_fallback_reason,
        )

        try:
            log(
                "tool",
                "Searching the simulated mailbox for the latest invoice.",
                tool="mailbox.search_latest_invoice",
            )
            invoice = self.mailbox.search_latest_invoice(run.plan.company)
            run.evidence.append(
                Evidence(
                    type="mail",
                    label=invoice["subject"],
                    reference=invoice["id"],
                    metadata={"received_at": invoice["received_at"]},
                )
            )
            log(
                "observation",
                f"Found {invoice['invoice_number']} from {invoice['company']}.",
                invoice_number=invoice["invoice_number"],
            )

            log("tool", "Extracting the amount and due date.", tool="invoice.extract")
            extracted = self.extractor.extract(invoice)
            run.evidence.append(
                Evidence(
                    type="extraction",
                    label=f"{extracted['currency']} {extracted['amount']:.2f} due {extracted['due_date']}",
                    reference=extracted["invoice_number"],
                )
            )
            log("observation", "Structured invoice fields were extracted.", **extracted)

            saved: LedgerRecord | None = None
            for attempt in range(1, 3):
                try:
                    log(
                        "tool",
                        f"Writing to the internal ledger (attempt {attempt}/2).",
                        tool="ledger.save",
                        attempt=attempt,
                    )
                    saved = self.ledger.save(extracted, run.id)
                    break
                except ToolError as error:
                    log(
                        "failure",
                        str(error),
                        code=error.code,
                        retryable=error.retryable,
                        attempt=attempt,
                    )
                    if not error.retryable or attempt == 2:
                        raise
                    log(
                        "retry",
                        "The failure is retryable; retrying once within policy.",
                        next_attempt=attempt + 1,
                    )
            if not saved:
                raise ToolError("Ledger did not return a record.", "WRITE_FAILED")
            run.evidence.append(
                Evidence(
                    type="ledger",
                    label="Existing ledger entry reused"
                    if saved.already_existed
                    else "Ledger entry created",
                    reference=saved.id,
                )
            )
            log(
                "observation",
                "The ledger write returned a record.",
                ledger_id=saved.id,
                already_existed=saved.already_existed,
            )

            log("tool", "Verifying the persisted outcome independently.", tool="ledger.verify")
            verified = self.ledger.verify(extracted["invoice_number"])
            if (
                not verified
                or verified.amount != extracted["amount"]
                or verified.due_date != extracted["due_date"]
            ):
                raise ToolError(
                    "Verification failed: the ledger record differs from the source invoice.",
                    "VERIFICATION_FAILED",
                )
            verified.already_existed = saved.already_existed
            run.status = RunStatus.COMPLETED
            run.result = verified
            run.summary = f"{verified.invoice_number} was entered and independently verified in the internal ledger."
            run.evidence.append(
                Evidence(
                    type="verification",
                    label="Ledger amount and due date match the source invoice",
                    reference=verified.id,
                )
            )
            log(
                "verified",
                "Outcome verified against the persisted ledger record.",
                ledger_id=verified.id,
            )
        except ToolError as error:
            run.status = RunStatus.FAILED
            run.summary = f"The worker stopped without claiming completion: {error}"
            log("failed", run.summary, code=error.code)
        return self._finish(run)

    def _finish(self, run: RunResponse) -> RunResponse:
        run.completed_at = self.now()
        self.database.save_run(run)
        return run
