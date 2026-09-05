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

    proposal = client.post(
        "/api/proposals",
        json={
            "intent_id": intent_id,
            "idempotency_key": "prepare-test-001",
            "expected_version": 1,
        },
    )
    assert proposal.status_code == 200
    assert proposal.json()["state"] == "VERIFIED"
    proposal_id = proposal.json()["proposal"]["proposal_id"]

    early_start = client.post(
        "/api/missions/not-approved/start",
        json={
            "actor": "operator-test",
            "idempotency_key": "start-early-001",
            "expected_version": 1,
        },
    )
    assert early_start.status_code == 422

    approved = client.post(
        f"/api/proposals/{proposal_id}/approve",
        json={
            "actor": "approver-test",
            "idempotency_key": "approve-test-001",
            "expected_version": 2,
        },
    )
    assert approved.status_code == 200
    assert approved.json()["state"] == "APPROVED"
    mission_id = approved.json()["mission"]["mission_id"]

    started = client.post(
        f"/api/missions/{mission_id}/start",
        json={
            "actor": "operator-test",
            "idempotency_key": "start-test-001",
            "expected_version": 3,
        },
    )
    assert started.json()["state"] == "EXECUTING"
    stopped = client.post(
        f"/api/missions/{mission_id}/stop",
        json={
            "actor": "safety-test",
            "idempotency_key": "stop-test-001",
            "expected_version": 4,
        },
    )
    assert stopped.json()["state"] == "SAFE_STOP"
    assert stopped.json()["stop_latency_ms"] < 200

    completed = client.post(
        f"/api/missions/{mission_id}/replan",
        json={
            "actor": "operator-test",
            "idempotency_key": "replan-test-001",
            "expected_version": 5,
        },
    )
    assert completed.status_code == 200
    assert completed.json()["state"] == "COMPLETED"
    assert completed.json()["mission"]["status"] == "COMPLETED"

    trace_id = completed.json()["trace_id"]
    trace = client.get(f"/api/traces/{trace_id}")
    assert trace.status_code == 200
    assert any(event["kind"] == "outcome.completed" for event in trace.json())


def test_ambiguous_fixture_intent_requires_clarification() -> None:
    response = TestClient(app).post(
        "/api/intents",
        json={
            "operator_text": "Please move the pallet to the rack",
            "operator_id": "operator-test",
            "provider": "fixture",
        },
    )
    assert response.status_code == 422
    assert "NEEDS_INPUT" in response.json()["detail"]


def test_api_reject_is_idempotent_and_version_guarded() -> None:
    client = TestClient(app)
    intent = client.post(
        "/api/intents",
        json={
            "operator_text": "Move P-104 from INBOUND-01 to RACK-A12",
            "operator_id": "operator-reject",
            "provider": "fixture",
        },
    ).json()
    proposal = client.post(
        "/api/proposals",
        json={
            "intent_id": intent["intent_id"],
            "idempotency_key": "prepare-reject-001",
            "expected_version": 1,
        },
    ).json()
    proposal_id = proposal["proposal"]["proposal_id"]
    payload = {
        "actor": "approver-reject",
        "reason": "route needs supervisor review",
        "idempotency_key": "reject-test-001",
        "expected_version": 2,
    }
    first = client.post(f"/api/proposals/{proposal_id}/reject", json=payload)
    second = client.post(f"/api/proposals/{proposal_id}/reject", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["state"] == second.json()["state"] == "REJECTED"
    assert first.json()["version"] == second.json()["version"] == 3

    stale = client.post(
        f"/api/proposals/{proposal_id}/approve",
        json={
            "actor": "approver-reject",
            "idempotency_key": "approve-stale-001",
            "expected_version": 2,
        },
    )
    assert stale.status_code == 409
