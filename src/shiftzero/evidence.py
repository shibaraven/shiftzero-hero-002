from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_core import to_jsonable_python

from shiftzero.domain import canonical_hash, utc_now


class EvidenceRecorder:
    """Append-only JSONL trace with a tamper-evident hash chain."""

    def __init__(self, root: Path, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or f"TR-{uuid.uuid4().hex[:12].upper()}"
        self.directory = root / self.trace_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self.path = self.directory / "hero-run.jsonl"
        self._previous_hash = "GENESIS"
        self._sequence = 0

    def record(self, kind: str, payload: BaseModel | dict[str, Any]) -> str:
        self._sequence += 1
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(mode="json")
        payload = to_jsonable_python(payload)
        span = {
            "trace_id": self.trace_id,
            "sequence": self._sequence,
            "recorded_at": utc_now().isoformat(),
            "kind": kind,
            "payload": payload,
            "previous_hash": self._previous_hash,
        }
        span_hash = canonical_hash(span)
        span["span_hash"] = span_hash
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(span, ensure_ascii=False, sort_keys=True) + "\n")
        self._previous_hash = span_hash
        return f"trace:{self.trace_id}:{self._sequence}:{span_hash}"

    @staticmethod
    def verify(path: Path) -> bool:
        previous_hash = "GENESIS"
        expected_sequence = 1
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                span = json.loads(line)
                stored_hash = span.pop("span_hash")
                if span["sequence"] != expected_sequence:
                    return False
                if span["previous_hash"] != previous_hash:
                    return False
                if canonical_hash(span) != stored_hash:
                    return False
                previous_hash = stored_hash
                expected_sequence += 1
        return expected_sequence > 1
