from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic_core import to_jsonable_python

from shiftzero.domain import canonical_hash, utc_now


class LedgerConflictError(RuntimeError):
    pass


class SqliteOperationLedger:
    """Durable exact-response idempotency receipts plus append-only decision audit."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def execute(
        self,
        *,
        operation: str,
        idempotency_key: str,
        fingerprint: str,
        callback: Callable[[], dict[str, Any]],
    ) -> tuple[dict[str, Any], bool]:
        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
        with self._lock, self._connect() as connection:
            existing = connection.execute(
                "SELECT fingerprint, status, response_json FROM operation_receipts "
                "WHERE operation = ? AND key_hash = ?",
                (operation, key_hash),
            ).fetchone()
            if existing is not None:
                prior_fingerprint, status, response_json = existing
                if prior_fingerprint != fingerprint:
                    raise LedgerConflictError(
                        "idempotency key was reused with different authenticated input"
                    )
                if status == "COMMITTED" and response_json is not None:
                    return json.loads(response_json), True
                raise LedgerConflictError("matching operation is already in progress")
            connection.execute(
                "INSERT INTO operation_receipts "
                "(operation, key_hash, fingerprint, status, created_at, updated_at) "
                "VALUES (?, ?, ?, 'PENDING', ?, ?)",
                (
                    operation,
                    key_hash,
                    fingerprint,
                    utc_now().isoformat(),
                    utc_now().isoformat(),
                ),
            )
            connection.commit()
        try:
            response = to_jsonable_python(callback())
        except Exception:
            with self._lock, self._connect() as connection:
                connection.execute(
                    "DELETE FROM operation_receipts WHERE operation = ? AND key_hash = ?",
                    (operation, key_hash),
                )
                connection.commit()
            raise
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE operation_receipts SET status = 'COMMITTED', response_json = ?, "
                "updated_at = ? WHERE operation = ? AND key_hash = ?",
                (
                    json.dumps(response, ensure_ascii=False, sort_keys=True),
                    utc_now().isoformat(),
                    operation,
                    key_hash,
                ),
            )
            connection.commit()
        return response, False

    def append_audit(
        self,
        *,
        operation: str,
        actor: str,
        role: str,
        resource_id: str,
        decision: str,
        payload: dict[str, Any],
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO decision_audit "
                "(recorded_at, operation, actor, role, resource_id, decision, payload_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    utc_now().isoformat(),
                    operation,
                    actor,
                    role,
                    resource_id,
                    decision,
                    canonical_hash(payload),
                ),
            )
            connection.commit()

    def list_audit(self, *, limit: int = 100) -> list[dict[str, Any]]:
        bounded_limit = min(max(limit, 1), 500)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT sequence, recorded_at, operation, actor, role, resource_id, "
                "decision, payload_hash FROM decision_audit ORDER BY sequence DESC LIMIT ?",
                (bounded_limit,),
            ).fetchall()
        keys = (
            "sequence",
            "recorded_at",
            "operation",
            "actor",
            "role",
            "resource_id",
            "decision",
            "payload_hash",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS operation_receipts (
                    operation TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('PENDING', 'COMMITTED')),
                    response_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (operation, key_hash)
                );
                CREATE TABLE IF NOT EXISTS decision_audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_at TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    role TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    payload_hash TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection
