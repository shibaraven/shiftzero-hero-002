from fastapi.testclient import TestClient

from shiftzero.api import app


def test_health_exposes_frozen_safety_policy() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "safety_policy": "safety-v1"}


def test_nebius_request_without_key_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    response = TestClient(app).post(
        "/api/hero-runs",
        json={
            "provider": "nebius",
            "approval_actor": "test-approver",
        },
    )
    assert response.status_code == 422
    assert "NEBIUS_API_KEY is required" in response.json()["detail"]


def test_interactive_api_enforces_approval_and_completes_replan() -> None:
    client = TestClient(app)
    intent = client.post(
        "/api/intents",
        json={
            "operator_text": "Move P-104 from INBOUND-01 to RACK-A12",
            "operator_id": "operator-test",
            "provider": "fixture",
        },
    )
    assert intent.status_code == 200
    intent_id = intent.json()["intent_id"]

    proposal = client.post("/api/proposals", json={"intent_id": intent_id})
    assert proposal.status_code == 200
    assert proposal.json()["state"] == "VERIFIED"
    proposal_id = proposal.json()["proposal"]["proposal_id"]

    early_start = client.post("/api/missions/not-approved/start")
    assert early_start.status_code == 422

    approved = client.post(f"/api/proposals/{proposal_id}/approve", json={"actor": "approver-test"})
    assert approved.status_code == 200
    assert approved.json()["state"] == "APPROVED"
    mission_id = approved.json()["mission"]["mission_id"]

    started = client.post(f"/api/missions/{mission_id}/start")
    assert started.json()["state"] == "EXECUTING"
    stopped = client.post(f"/api/missions/{mission_id}/stop", json={"actor": "safety-test"})
    assert stopped.json()["state"] == "SAFE_STOP"
    assert stopped.json()["stop_latency_ms"] < 200

    completed = client.post(f"/api/missions/{mission_id}/replan")
    assert completed.status_code == 200
    assert completed.json()["state"] == "COMPLETED"
    assert completed.json()["mission"]["status"] == "COMPLETED"

    trace_id = completed.json()["trace_id"]
    trace = client.get(f"/api/traces/{trace_id}")
    assert trace.status_code == 200
    assert trace.json()[-1]["kind"] == "outcome.completed"
