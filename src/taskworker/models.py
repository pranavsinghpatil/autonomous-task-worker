from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_CLARIFICATION = "awaiting_clarification"


class ActionName(StrEnum):
    SEARCH_MAILBOX = "search_mailbox"
    EXTRACT_FIELDS = "extract_fields"
    WRITE_LEDGER = "write_ledger"
    VERIFY_LEDGER = "verify_ledger"


ALLOWED_ACTIONS = [
    ActionName.SEARCH_MAILBOX,
    ActionName.EXTRACT_FIELDS,
    ActionName.WRITE_LEDGER,
    ActionName.VERIFY_LEDGER,
]


class TaskRequest(BaseModel):
    task: str = Field(min_length=5, max_length=2000)

    @field_validator("task")
    @classmethod
    def strip_task(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Task cannot be blank.")
        return cleaned


class PlannedAction(BaseModel):
    name: ActionName
    label: str
    tool: str
    retry_limit: int = Field(default=0, ge=0, le=1)


class InvoicePlan(BaseModel):
    company: str = Field(min_length=2, max_length=120)
    requested_fields: list[Literal["amount", "due_date"]] = ["amount", "due_date"]
    actions: list[PlannedAction]
    rationale: str = Field(min_length=3, max_length=500)

    @field_validator("actions")
    @classmethod
    def validate_action_order(cls, value: list[PlannedAction]) -> list[PlannedAction]:
        if [action.name for action in value] != ALLOWED_ACTIONS:
            raise ValueError(
                "Plans must contain the four allowlisted actions in their required order."
            )
        return value


class PlannerResult(BaseModel):
    plan: InvoicePlan
    provider: str
    fallback_reason: str | None = None


class Event(BaseModel):
    timestamp: str
    type: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    type: str
    label: str
    reference: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class LedgerRecord(BaseModel):
    id: str
    invoice_number: str
    company: str
    amount: float
    currency: str
    due_date: str
    source_message_id: str
    entered_at: str
    already_existed: bool = False


class RunResponse(BaseModel):
    id: str
    task: str
    status: RunStatus
    planner_provider: str
    planner_fallback_reason: str | None = None
    started_at: str
    completed_at: str | None = None
    summary: str
    plan: InvoicePlan | None = None
    events: list[Event] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    result: LedgerRecord | None = None
