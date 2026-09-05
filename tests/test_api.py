import pytest
from fastapi.testclient import TestClient

from shiftzero.api import _ledgers, app
from shiftzero.auth import AuthSettings, issue_access_token

AUTH_SECRET = "test-only-auth-secret-with-at-least-32-characters"


@pytest.fixture(autouse=True)
def configured_auth(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SHIFTZERO_AUTH_SECRET", AUTH_SECRET)
    monkeypatch.setenv("SHIFTZERO_LEDGER_PATH", str(tmp_path / "agent-api.sqlite3"))
    _ledgers.clear()


def _authorization(role: str, subject: str = "api-test") -> dict[str, str]:
    token = issue_access_token(
        subject=subject,
        role=role,  # type: ignore[arg-type]
        settings=AuthSettings(secret=AUTH_SECRET.encode()),
    )
    return {"Authorization": f"Bearer {token}"}


def test_health_exposes_frozen_safety_policy() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "safety_policy": "safety-v2"}


def test_nebius_request_without_key_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    response = TestClient(app).post(
        "/api/hero-runs",
        json={
            "provider": "nebius",
            "idempotency_key": "hero-nebius-test-001",
            "expected_version": 0,
        },
        headers=_authorization("approver"),
    )
    assert response.status_code == 422
    assert "NEBIUS_API_KEY is required" in response.json()["detail"]


def test_interactive_api_enforces_approval_and_completes_replan() -> None:
    client = TestClient(app)
    intent = client.post(
        "/api/intents",
        json={
            "operator_text": "Move P-104 from INBOUND-01 to RACK-A12",
            "provider": "fixture",
            "idempotency_key": "intent-test-001",
            "expected_version": 0,
        },
        headers=_authorization("operator", "operator-test"),
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
        headers=_authorization("operator", "operator-test"),
    )
    assert proposal.status_code == 200
    assert proposal.json()["state"] == "VERIFIED"
    proposal_id = proposal.json()["proposal"]["proposal_id"]

    early_start = client.post(
        "/api/missions/not-approved/start",
        json={
            "idempotency_key": "start-early-001",
            "expected_version": 1,
        },
        headers=_authorization("executor", "executor-test"),
    )
    assert early_start.status_code == 422

    approved = client.post(
        f"/api/proposals/{proposal_id}/approve",
        json={
            "idempotency_key": "approve-test-001",
            "expected_version": 2,
        },
        headers=_authorization("approver", "approver-test"),
    )
    assert approved.status_code == 200
    assert approved.json()["state"] == "APPROVED"
    mission_id = approved.json()["mission"]["mission_id"]

    started = client.post(
        f"/api/missions/{mission_id}/start",
        json={
            "idempotency_key": "start-test-001",
            "expected_version": 3,
        },
        headers=_authorization("executor", "executor-test"),
    )
    assert started.json()["state"] == "EXECUTING"
    status = client.get(f"/api/missions/{mission_id}")
    assert status.status_code == 200
    assert status.json()["mission"]["status"] == "EXECUTING"
    stopped = client.post(
        f"/api/missions/{mission_id}/stop",
        json={
            "idempotency_key": "stop-test-001",
            "expected_version": 4,
            "trigger_source": "safety-panel-test",
        },
        headers=_authorization("safety", "safety-test"),
    )
    assert stopped.json()["state"] == "SAFE_STOP"
    assert stopped.json()["stop_latency_ms"] < 200

    replanned = client.post(
        f"/api/missions/{mission_id}/replan",
        json={
            "idempotency_key": "replan-test-001",
            "expected_version": 5,
        },
        headers=_authorization("operator", "operator-test"),
    )
    assert replanned.status_code == 200
    assert replanned.json()["state"] == "VERIFIED"

    completed = client.post(
        f"/api/missions/{mission_id}/resume",
        json={
            "idempotency_key": "resume-test-001",
            "expected_version": 6,
        },
        headers=_authorization("executor", "executor-test"),
    )
    assert completed.status_code == 200
    assert completed.json()["state"] == "COMPLETED"
    assert completed.json()["mission"]["status"] == "COMPLETED"

    trace_id = completed.json()["trace_id"]
    trace = client.get(f"/api/traces/{trace_id}")
    assert trace.status_code == 200
    assert any(event["kind"] == "outcome.completed" for event in trace.json())
    metrics_events = [
        event for event in trace.json() if event["kind"] == "tool.get_operation_metrics"
    ]
    assert len(metrics_events) == 1
    assert metrics_events[0]["payload"]["result"]["completed"] is True
    assert any(event["kind"] == "tool.get_mission_status" for event in trace.json())
    proof = next(event["payload"] for event in trace.json() if event["kind"] == "safety.proof")
    assert next(
        check for check in proof["checks"] if check["name"] == "approval_integrity"
    )["passed"] is True


def test_ambiguous_fixture_intent_requires_clarification() -> None:
    response = TestClient(app).post(
        "/api/intents",
        json={
            "operator_text": "Please move the pallet to the rack",
            "provider": "fixture",
            "idempotency_key": "intent-ambiguous-001",
            "expected_version": 0,
        },
        headers=_authorization("operator", "operator-test"),
    )
    assert response.status_code == 422
    assert "NEEDS_INPUT" in response.json()["detail"]


def test_api_reject_is_idempotent_and_version_guarded() -> None:
    client = TestClient(app)
    intent = client.post(
        "/api/intents",
        json={
            "operator_text": "Move P-104 from INBOUND-01 to RACK-A12",
            "provider": "fixture",
            "idempotency_key": "intent-reject-001",
            "expected_version": 0,
        },
        headers=_authorization("operator", "operator-reject"),
    ).json()
    proposal = client.post(
        "/api/proposals",
        json={
            "intent_id": intent["intent_id"],
            "idempotency_key": "prepare-reject-001",
            "expected_version": 1,
        },
        headers=_authorization("operator", "operator-reject"),
    ).json()
    proposal_id = proposal["proposal"]["proposal_id"]
    payload = {
        "reason": "route needs supervisor review",
        "idempotency_key": "reject-test-001",
        "expected_version": 2,
    }
    first = client.post(
        f"/api/proposals/{proposal_id}/reject",
        json=payload,
        headers=_authorization("approver", "approver-reject"),
    )
    second = client.post(
        f"/api/proposals/{proposal_id}/reject",
        json=payload,
        headers=_authorization("approver", "approver-reject"),
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["state"] == second.json()["state"] == "REJECTED"
    assert first.json()["version"] == second.json()["version"] == 3

    stale = client.post(
        f"/api/proposals/{proposal_id}/approve",
        json={
            "idempotency_key": "approve-stale-001",
            "expected_version": 2,
        },
        headers=_authorization("approver", "approver-reject"),
    )
    assert stale.status_code == 409


def test_authenticated_role_cannot_be_self_asserted() -> None:
    client = TestClient(app)
    intent = client.post(
        "/api/intents",
        json={
            "operator_text": "Move P-104 from INBOUND-01 to RACK-A12",
            "provider": "fixture",
            "idempotency_key": "intent-rbac-001",
            "expected_version": 0,
        },
        headers=_authorization("operator", "operator-rbac"),
    ).json()
    proposal = client.post(
        "/api/proposals",
        json={
            "intent_id": intent["intent_id"],
            "idempotency_key": "prepare-rbac-001",
            "expected_version": 1,
        },
        headers=_authorization("operator", "operator-rbac"),
    ).json()
    response = client.post(
        f"/api/proposals/{proposal['proposal']['proposal_id']}/approve",
        json={"idempotency_key": "approve-rbac-001", "expected_version": 2},
        headers=_authorization("operator", "operator-rbac"),
    )
    assert response.status_code == 403


def test_create_intent_is_durably_idempotent() -> None:
    client = TestClient(app)
    payload = {
        "operator_text": "Move P-104 from INBOUND-01 to RACK-A12",
        "provider": "fixture",
        "idempotency_key": "intent-idempotent-001",
        "expected_version": 0,
    }
    headers = _authorization("operator", "operator-idempotent")
    first = client.post("/api/intents", json=payload, headers=headers)
    _ledgers.clear()
    second = client.post("/api/intents", json=payload, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_every_write_contract_has_idempotency_version_and_no_self_asserted_role() -> None:
    openapi = app.openapi()
    schemas = openapi["components"]["schemas"]
    for path, operations in openapi["paths"].items():
        for method, operation in operations.items():
            if method.lower() not in {"post", "put", "patch", "delete"}:
                continue
            body_schema = operation["requestBody"]["content"]["application/json"]["schema"]
            name = body_schema["$ref"].rsplit("/", 1)[-1]
            properties = schemas[name]["properties"]
            required = set(schemas[name]["required"])
            assert {"idempotency_key", "expected_version"} <= required, path
            assert "actor_role" not in properties, path
            assert "actor" not in properties, path
