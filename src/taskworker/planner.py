from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import ValidationError

from taskworker.config import Settings
from taskworker.models import ActionName, InvoicePlan, PlannedAction, PlannerResult

SYSTEM_PROMPT = """You are the planning component of a sandboxed invoice-intake worker.
Return JSON only. The worker can only process an invoice already present in its simulated mailbox.
Choose one supplier from the provided list. Never plan payments, transfers, approvals, email sends,
or actions outside invoice intake. Use exactly these actions in this exact order:
search_mailbox, extract_fields, write_ledger, verify_ledger."""


def default_actions() -> list[PlannedAction]:
    return [
        PlannedAction(
            name=ActionName.SEARCH_MAILBOX,
            label="Find the latest matching invoice",
            tool="mailbox.search_latest_invoice",
        ),
        PlannedAction(
            name=ActionName.EXTRACT_FIELDS,
            label="Extract amount and due date",
            tool="invoice.extract",
        ),
        PlannedAction(
            name=ActionName.WRITE_LEDGER,
            label="Enter the invoice in the internal ledger",
            tool="ledger.save",
            retry_limit=1,
        ),
        PlannedAction(
            name=ActionName.VERIFY_LEDGER,
            label="Verify the final ledger entry",
            tool="ledger.verify",
        ),
    ]


class PlannerError(RuntimeError):
    pass


class Planner(ABC):
    @abstractmethod
    def plan(self, task: str, suppliers: list[str]) -> PlannerResult:
        raise NotImplementedError


class OfflinePlanner(Planner):
    def __init__(self, reason: str | None = None) -> None:
        self.reason = reason

    def plan(self, task: str, suppliers: list[str]) -> PlannerResult:
        match = next((supplier for supplier in suppliers if supplier.lower() in task.lower()), None)
        if not match:
            raise PlannerError("No recognized sandbox supplier was named in the task.")
        return PlannerResult(
            provider="offline",
            fallback_reason=self.reason,
            plan=InvoicePlan(
                company=match,
                requested_fields=["amount", "due_date"],
                actions=default_actions(),
                rationale="Matched a named sandbox supplier and selected the fixed invoice-intake workflow.",
            ),
        )


def validate_model_plan(
    payload: dict[str, Any], suppliers: list[str], provider: str
) -> PlannerResult:
    plan = InvoicePlan.model_validate(payload)
    supplier = next((item for item in suppliers if item.lower() == plan.company.lower()), None)
    if not supplier:
        raise PlannerError("The model selected a supplier outside the sandbox allowlist.")
    plan.company = supplier
    return PlannerResult(plan=plan, provider=provider)


class GroqPlanner(Planner):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def plan(self, task: str, suppliers: list[str]) -> PlannerResult:
        schema = InvoicePlan.model_json_schema()
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"task": task, "suppliers": suppliers, "schema": schema}
                        ),
                    },
                ],
            },
            timeout=15,
        )
        response.raise_for_status()
        try:
            payload = json.loads(response.json()["choices"][0]["message"]["content"])
            return validate_model_plan(payload, suppliers, "groq")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as error:
            raise PlannerError(f"Groq returned an invalid plan: {error}") from error


class GeminiPlanner(Planner):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def plan(self, task: str, suppliers: list[str]) -> PlannerResult:
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json={
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": json.dumps({"task": task, "suppliers": suppliers})}],
                    }
                ],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
            },
            timeout=15,
        )
        response.raise_for_status()
        try:
            payload = json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"])
            return validate_model_plan(payload, suppliers, "gemini")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as error:
            raise PlannerError(f"Gemini returned an invalid plan: {error}") from error


class ResilientPlanner(Planner):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def plan(self, task: str, suppliers: list[str]) -> PlannerResult:
        preferred = self.settings.planner_provider
        candidates: list[Planner] = []
        if preferred in {"auto", "groq"} and self.settings.groq_api_key:
            candidates.append(GroqPlanner(self.settings.groq_api_key, self.settings.groq_model))
        if preferred in {"auto", "groq", "gemini"} and self.settings.gemini_api_key:
            candidates.append(
                GeminiPlanner(self.settings.gemini_api_key, self.settings.gemini_model)
            )
        reasons: list[str] = []
        for planner in candidates:
            try:
                return planner.plan(task, suppliers)
            except (httpx.HTTPError, PlannerError) as error:
                reasons.append(str(error))
        if preferred in {"groq", "gemini"} and not candidates:
            reasons.append(f"{preferred.title()} was selected but its API key is not configured")
        return OfflinePlanner("; ".join(reasons) or "No online planner is configured").plan(
            task, suppliers
        )
