from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from taskworker.database import Database
from taskworker.models import LedgerRecord


class ToolError(RuntimeError):
    def __init__(self, message: str, code: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class MailboxTool:
    def __init__(self, database: Database) -> None:
        self.database = database

    def search_latest_invoice(self, company: str) -> dict[str, Any]:
        invoice = self.database.latest_invoice(company)
        if not invoice:
            raise ToolError(f"No sandbox invoice was found for {company}.", "INVOICE_NOT_FOUND")
        return invoice


class InvoiceExtractorTool:
    def extract(self, invoice: dict[str, Any]) -> dict[str, Any]:
        return {
            "invoice_number": invoice["invoice_number"],
            "company": invoice["company"],
            "amount": float(invoice["amount"]),
            "currency": invoice["currency"],
            "due_date": invoice["due_date"],
            "source_message_id": invoice["id"],
        }


class InternalLedgerTool:
    def __init__(self, database: Database, *, fail_first_write: bool = True) -> None:
        self.database = database
        self.fail_first_write = fail_first_write
        self.failed_runs: set[str] = set()

    def save(self, extracted: dict[str, Any], run_id: str) -> LedgerRecord:
        if self.fail_first_write and run_id not in self.failed_runs:
            self.failed_runs.add(run_id)
            raise ToolError(
                "Internal ledger is temporarily unavailable (simulated 503).",
                "TRANSIENT_WRITE_FAILURE",
                retryable=True,
            )
        record = LedgerRecord(
            id=f"ledger-{uuid4().hex[:8]}",
            **extracted,
            entered_at=datetime.now(UTC).isoformat(),
        )
        return self.database.save_ledger_record(record)

    def verify(self, invoice_number: str) -> LedgerRecord | None:
        return self.database.find_ledger_record(invoice_number)
