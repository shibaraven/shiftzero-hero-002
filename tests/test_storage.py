from pathlib import Path

import pytest

from shiftzero.storage import LedgerConflictError, SqliteOperationLedger


def test_sqlite_ledger_replays_exact_response_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite3"
    calls = 0

    def operation() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"resource": "INT-001", "version": 1}

    first, replayed_first = SqliteOperationLedger(path).execute(
        operation="intent:create",
        idempotency_key="stable-key",
        fingerprint="same-input",
        callback=operation,
    )
    second, replayed_second = SqliteOperationLedger(path).execute(
        operation="intent:create",
        idempotency_key="stable-key",
        fingerprint="same-input",
        callback=operation,
    )
    assert first == second
    assert replayed_first is False
    assert replayed_second is True
    assert calls == 1

    with pytest.raises(LedgerConflictError, match="different authenticated input"):
        SqliteOperationLedger(path).execute(
            operation="intent:create",
            idempotency_key="stable-key",
            fingerprint="different-input",
            callback=operation,
        )


def test_decision_audit_is_append_only_and_hashes_payload(tmp_path: Path) -> None:
    ledger = SqliteOperationLedger(tmp_path / "ledger.sqlite3")
    ledger.append_audit(
        operation="proposal:TP-1:approve",
        actor="alice",
        role="approver",
        resource_id="TP-1",
        decision="APPROVE",
        payload={"proposal_id": "TP-1"},
    )
    rows = ledger.list_audit()
    assert len(rows) == 1
    assert rows[0]["actor"] == "alice"
    assert rows[0]["decision"] == "APPROVE"
    assert len(rows[0]["payload_hash"]) == 64
