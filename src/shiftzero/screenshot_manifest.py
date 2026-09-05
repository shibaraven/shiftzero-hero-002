from __future__ import annotations

import hashlib
import json
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shiftzero.domain import canonical_hash

SCREENSHOT_FILES = (
    "01-completed.png",
    "02-model-tool-call.png",
    "03-verified-proof.png",
)


def build_screenshot_manifest(*, root: Path, output_path: Path) -> dict[str, Any]:
    summary = json.loads((root / "evidence/hero-summary.json").read_text(encoding="utf-8"))
    visible_timestamp = summary["evidence_captured_at"]
    rows: list[dict[str, Any]] = []
    for name in SCREENSHOT_FILES:
        path = root / "evidence" / "screenshots" / name
        content = path.read_bytes()
        if not content.startswith(b"\x89PNG\r\n\x1a\n") or len(content) < 24:
            raise ValueError(f"screenshot is not a valid PNG: {path}")
        width, height = struct.unpack(">II", content[16:24])
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "width_px": width,
                "height_px": height,
                "captured_at_utc": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
                "visible_timestamp_text": f"EVIDENCE UTC {visible_timestamp}",
                "visible_scope_label": "MOCK / FIXTURE",
            }
        )
    body: dict[str, Any] = {
        "manifest_version": "evidence-screenshots-v1",
        "measurement_scope": "local_production_build_reference_simulator_fixture_provider",
        "visible_timestamp_source": "verified hero trace outcome event",
        "screenshots": rows,
    }
    body["manifest_hash"] = canonical_hash(body)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return body
