from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from taskworker.models import (
    Event,
    Evidence,
    InboxInvoice,
    LedgerRecord,
    RunResponse,
    RunStatus,
    RunSummary,
)

SEED_INVOICES = (
    {
        "id": "mail-1042",
        "company": "Acme Supplies",
        "invoice_number": "ACME-2026-0918",
        "amount": 1280.50,
        "currency": "USD",
        "due_date": "2026-10-20",
        "received_at": "2026-10-01T09:14:00+00:00",
        "subject": "Invoice ACME-2026-0918 — September supplies",
    },
    {
        "id": "mail-1034",
        "company": "Acme Supplies",
        "invoice_number": "ACME-2026-0827",
        "amount": 940.00,
        "currency": "USD",
        "due_date": "2026-09-30",
        "received_at": "2026-09-03T08:00:00+00:00",
        "subject": "Invoice ACME-2026-0827",
    },
    {
        "id": "mail-1057",
        "company": "Northwind Logistics",
        "invoice_number": "NW-4419",
        "amount": 675.25,
        "currency": "USD",
        "due_date": "2026-10-15",
        "received_at": "2026-10-02T14:22:00+00:00",
        "subject": "Northwind Logistics invoice NW-4419",
    },
    {
        "id": "mail-1059",
        "company": "Contoso Cloud",
        "invoice_number": "CONT-7732",
        "amount": 2120.00,
        "currency": "USD",
        "due_date": "2026-10-31",
        "received_at": "2026-10-03T06:45:00+00:00",
        "subject": "Contoso Cloud — October invoice",
    },
    {
        "id": "mail-1052",
        "company": "Northwind Logistics",
        "invoice_number": "NW-4391",
        "amount": 512.75,
        "currency": "USD",
        "due_date": "2026-09-28",
        "received_at": "2026-09-11T11:36:00+00:00",
        "subject": "Northwind freight services invoice NW-4391",
    },
    {
        "id": "mail-1026",
        "company": "Contoso Cloud",
        "invoice_number": "CONT-7644",
        "amount": 1980.00,
        "currency": "USD",
        "due_date": "2026-09-30",
        "received_at": "2026-09-02T15:10:00+00:00",
        "subject": "Contoso Cloud — September platform usage",
    },
    {
        "id": "mail-1018",
        "company": "Acme Supplies",
        "invoice_number": "ACME-2026-0721",
        "amount": 760.40,
        "currency": "USD",
        "due_date": "2026-08-25",
        "received_at": "2026-08-05T08:42:00+00:00",
        "subject": "Invoice ACME-2026-0721 — office replenishment",
    },
)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS invoices (
                  id TEXT PRIMARY KEY, company TEXT NOT NULL, invoice_number TEXT NOT NULL,
                  amount REAL NOT NULL, currency TEXT NOT NULL, due_date TEXT NOT NULL,
                  received_at TEXT NOT NULL, subject TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ledger_records (
                  id TEXT PRIMARY KEY, invoice_number TEXT NOT NULL UNIQUE, company TEXT NOT NULL,
                  amount REAL NOT NULL, currency TEXT NOT NULL, due_date TEXT NOT NULL,
                  source_message_id TEXT NOT NULL, entered_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY, task TEXT NOT NULL, status TEXT NOT NULL,
                  planner_provider TEXT NOT NULL, planner_fallback_reason TEXT,
                  started_at TEXT NOT NULL, completed_at TEXT, summary TEXT NOT NULL,
                  plan_json TEXT, result_json TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, timestamp TEXT NOT NULL,
                  type TEXT NOT NULL, message TEXT NOT NULL, details_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, type TEXT NOT NULL,
                  label TEXT NOT NULL, reference TEXT NOT NULL, metadata_json TEXT NOT NULL
                );
                """
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO invoices
                (id, company, invoice_number, amount, currency, due_date, received_at, subject)
                VALUES (:id, :company, :invoice_number, :amount, :currency, :due_date, :received_at, :subject)
                """,
                SEED_INVOICES,
            )

    def reset_demo(self) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM evidence")
            connection.execute("DELETE FROM events")
            connection.execute("DELETE FROM runs")
            connection.execute("DELETE FROM ledger_records")

    def latest_invoice(self, company: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM invoices WHERE lower(company) = lower(?)
                ORDER BY received_at DESC LIMIT 1
                """,
                (company,),
            ).fetchone()
            return dict(row) if row else None

    def supplier_names(self) -> list[str]:
        with self.connection() as connection:
            return [
                row["company"]
                for row in connection.execute("SELECT DISTINCT company FROM invoices")
            ]

    def list_invoices(self) -> list[InboxInvoice]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM invoices ORDER BY received_at DESC").fetchall()
        newest_by_supplier: dict[str, str] = {}
        for row in rows:
            newest_by_supplier.setdefault(row["company"].lower(), row["id"])
        return [
            InboxInvoice(
                **dict(row),
                is_latest_for_supplier=newest_by_supplier[row["company"].lower()] == row["id"],
            )
            for row in rows
        ]

    def save_ledger_record(self, record: LedgerRecord) -> LedgerRecord:
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM ledger_records WHERE invoice_number = ?", (record.invoice_number,)
            ).fetchone()
            if existing:
                return LedgerRecord(**dict(existing), already_existed=True)
            connection.execute(
                """
                INSERT INTO ledger_records
                (id, invoice_number, company, amount, currency, due_date, source_message_id, entered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.invoice_number,
                    record.company,
                    record.amount,
                    record.currency,
                    record.due_date,
                    record.source_message_id,
                    record.entered_at,
                ),
            )
        return record

    def find_ledger_record(self, invoice_number: str) -> LedgerRecord | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM ledger_records WHERE invoice_number = ?", (invoice_number,)
            ).fetchone()
            return LedgerRecord(**dict(row)) if row else None

    def list_ledger(self) -> list[LedgerRecord]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM ledger_records ORDER BY entered_at DESC"
            ).fetchall()
            return [LedgerRecord(**dict(row)) for row in rows]

    def list_recent_runs(self, limit: int = 6) -> list[RunSummary]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, task, status, planner_provider, started_at, completed_at, summary
                FROM runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [RunSummary(**dict(row)) for row in rows]

    def save_run(self, run: RunResponse) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO runs
                (id, task, status, planner_provider, planner_fallback_reason, started_at, completed_at,
                 summary, plan_json, result_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.task,
                    run.status.value,
                    run.planner_provider,
                    run.planner_fallback_reason,
                    run.started_at,
                    run.completed_at,
                    run.summary,
                    json.dumps(run.plan.model_dump(mode="json")) if run.plan else None,
                    json.dumps(run.result.model_dump(mode="json")) if run.result else None,
                ),
            )
            connection.execute("DELETE FROM events WHERE run_id = ?", (run.id,))
            connection.execute("DELETE FROM evidence WHERE run_id = ?", (run.id,))
            connection.executemany(
                """INSERT INTO events (run_id, timestamp, type, message, details_json)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (run.id, event.timestamp, event.type, event.message, json.dumps(event.details))
                    for event in run.events
                ],
            )
            connection.executemany(
                """INSERT INTO evidence (run_id, type, label, reference, metadata_json)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    (run.id, item.type, item.label, item.reference, json.dumps(item.metadata))
                    for item in run.evidence
                ],
            )

    def get_run(self, run_id: str) -> RunResponse | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                return None
            events = [
                Event(
                    timestamp=item["timestamp"],
                    type=item["type"],
                    message=item["message"],
                    details=json.loads(item["details_json"]),
                )
                for item in connection.execute(
                    "SELECT * FROM events WHERE run_id = ? ORDER BY id", (run_id,)
                )
            ]
            evidence = [
                Evidence(
                    type=item["type"],
                    label=item["label"],
                    reference=item["reference"],
                    metadata=json.loads(item["metadata_json"]),
                )
                for item in connection.execute(
                    "SELECT * FROM evidence WHERE run_id = ? ORDER BY id", (run_id,)
                )
            ]
            from taskworker.models import InvoicePlan

            return RunResponse(
                id=row["id"],
                task=row["task"],
                status=RunStatus(row["status"]),
                planner_provider=row["planner_provider"],
                planner_fallback_reason=row["planner_fallback_reason"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                summary=row["summary"],
                plan=InvoicePlan.model_validate_json(row["plan_json"])
                if row["plan_json"]
                else None,
                result=LedgerRecord.model_validate_json(row["result_json"])
                if row["result_json"]
                else None,
                events=events,
                evidence=evidence,
            )
