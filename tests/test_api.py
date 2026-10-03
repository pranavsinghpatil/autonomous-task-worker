from __future__ import annotations

from fastapi.testclient import TestClient


def test_task_and_evidence_api(app) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/tasks", json={"task": "Process the latest invoice from Acme Supplies."}
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "completed"
    assert run["planner_provider"] == "offline"
    assert any(event["type"] == "verified" for event in run["events"])

    stored = client.get(f"/api/runs/{run['id']}")
    assert stored.status_code == 200
    assert stored.json()["result"]["invoice_number"] == "ACME-2026-0918"
    assert len(client.get("/api/ledger").json()) == 1


def test_api_rejects_blank_task(app) -> None:
    response = TestClient(app).post("/api/tasks", json={"task": "   "})
    assert response.status_code == 422


def test_demo_reset_clears_ledger(app) -> None:
    client = TestClient(app)
    client.post("/api/tasks", json={"task": "Process the latest invoice from Acme Supplies."})
    assert client.get("/api/ledger").json()
    assert client.post("/api/demo/reset").status_code == 200
    assert client.get("/api/ledger").json() == []
