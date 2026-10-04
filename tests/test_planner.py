from __future__ import annotations

import httpx
import pytest

from taskworker.config import Settings
from taskworker.models import ActionName
from taskworker.planner import (
    OfflinePlanner,
    PlannerError,
    PlannerResult,
    ResilientPlanner,
    default_actions,
    validate_model_plan,
)

SUPPLIERS = ["Acme Supplies", "Northwind Logistics", "Contoso Cloud"]


def test_offline_planner_creates_allowlisted_plan() -> None:
    result = OfflinePlanner().plan("Process the latest invoice from Acme Supplies.", SUPPLIERS)
    assert result.provider == "offline"
    assert result.plan.company == "Acme Supplies"
    assert [action.name for action in result.plan.actions] == list(ActionName)


def test_offline_planner_requires_known_supplier() -> None:
    with pytest.raises(PlannerError):
        OfflinePlanner().plan("Process the latest invoice.", SUPPLIERS)


def test_invalid_model_action_order_is_rejected() -> None:
    payload = {
        "company": "Acme Supplies",
        "requested_fields": ["amount", "due_date"],
        "rationale": "Process the newest invoice.",
        "actions": [
            {
                "name": "extract_fields",
                "label": "Extract",
                "tool": "invoice.extract",
                "retry_limit": 0,
            },
        ],
    }
    with pytest.raises(PlannerError):
        validate_model_plan(payload, SUPPLIERS, "groq")


def test_model_plan_actions_are_normalized_to_safe_tool_contracts() -> None:
    payload = {
        "company": "Acme Supplies",
        "requested_fields": ["amount", "due_date"],
        "rationale": "Process the newest invoice.",
        "actions": [
            {"name": "search_mailbox"},
            {"name": "extract_fields"},
            {"name": "write_ledger"},
            {"name": "verify_ledger"},
        ],
    }
    result = validate_model_plan(payload, SUPPLIERS, "gemini")
    assert result.plan.actions == default_actions()


def test_auto_mode_without_credentials_is_labeled_offline(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "unused.db",
        planner_provider="auto",
        groq_api_key=None,
        groq_model="test",
        gemini_api_key=None,
        gemini_model="test",
        demo_transient_failure=True,
    )
    result = ResilientPlanner(settings).plan("Process Acme Supplies invoice.", SUPPLIERS)
    assert result.provider == "offline"
    assert result.fallback_reason == "No online planner is configured"


def test_groq_failure_uses_configured_gemini_fallback(tmp_path, monkeypatch) -> None:
    class FailedGroq:
        def __init__(self, *_: str) -> None:
            pass

        def plan(self, *_: object) -> PlannerResult:
            raise PlannerError("Groq unavailable")

    class WorkingGemini:
        def __init__(self, *_: str) -> None:
            pass

        def plan(self, _: str, suppliers: list[str]) -> PlannerResult:
            return PlannerResult(
                provider="gemini",
                plan={
                    "company": suppliers[0],
                    "requested_fields": ["amount", "due_date"],
                    "actions": default_actions(),
                    "rationale": "Gemini fallback created the validated plan.",
                },
            )

    monkeypatch.setattr("taskworker.planner.GroqPlanner", FailedGroq)
    monkeypatch.setattr("taskworker.planner.GeminiPlanner", WorkingGemini)
    settings = Settings(
        database_path=tmp_path / "unused.db",
        planner_provider="groq",
        groq_api_key="test-groq-key",
        groq_model="test",
        gemini_api_key="test-gemini-key",
        gemini_model="test",
        demo_transient_failure=True,
    )
    result = ResilientPlanner(settings).plan("Process Acme Supplies invoice.", SUPPLIERS)
    assert result.provider == "gemini"


def test_provider_error_reason_does_not_expose_request_url(tmp_path, monkeypatch) -> None:
    class FailedGroq:
        def __init__(self, *_: str) -> None:
            pass

        def plan(self, *_: object) -> PlannerResult:
            request = httpx.Request("POST", "https://api.example.test/?key=secret-value")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("unsafe diagnostic", request=request, response=response)

    monkeypatch.setattr("taskworker.planner.GroqPlanner", FailedGroq)
    settings = Settings(
        database_path=tmp_path / "unused.db",
        planner_provider="groq",
        groq_api_key="test-key",
        groq_model="test",
        gemini_api_key=None,
        gemini_model="test",
        demo_transient_failure=True,
    )
    result = ResilientPlanner(settings).plan("Process Acme Supplies invoice.", SUPPLIERS)
    assert result.provider == "offline"
    assert "secret-value" not in (result.fallback_reason or "")
    assert "HTTP 503" in (result.fallback_reason or "")
