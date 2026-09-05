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

FIXTURE_SCOPE_LABEL = "MOCK / FIXTURE"
FINAL_SCOPE_LABEL = "LIVE / NEBIUS"


def build_screenshot_manifest(*, root: Path, output_path: Path) -> dict[str, Any]:
    """Build a manifest for local preflight screenshots.

    This function deliberately cannot create a final competition manifest. Final screenshots
    require a passing live Compatibility Gate plus real provider receipt fields and must be
    validated with :func:`validate_final_screenshot_manifest`.
    """
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
                "visible_scope_label": FIXTURE_SCOPE_LABEL,
            }
        )
    body: dict[str, Any] = {
        "manifest_version": "evidence-screenshots-v1",
        "evidence_class": "preflight_fixture",
        "final_submission_eligible": False,
        "measurement_scope": "local_production_build_reference_simulator_fixture_provider",
        "provider": "fixture",
        "real_provider": False,
        "replacement_required_after_live_gate": True,
        "prohibited_use": (
            "These images must not be submitted or described as real Nebius/runtime evidence."
        ),
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


def validate_final_screenshot_manifest(
    *,
    root: Path,
    manifest_path: Path,
    compatibility_report_path: Path,
) -> dict[str, Any]:
    """Fail closed unless three screenshots are backed by a passing live-provider gate.

    The validator does not promote fixture images. A final manifest must be authored only after
    the real screenshots have replaced the preflight captures and must bind an exact model,
    request ID and trace ID to those files.
    """
    errors: list[str] = []
    manifest = _read_json(manifest_path, errors, "screenshot manifest")
    compatibility = _read_json(
        compatibility_report_path, errors, "live Compatibility Gate report"
    )

    if compatibility:
        if compatibility.get("official_gate_passed") is not True:
            errors.append("live Compatibility Gate is not officially passed")
        if compatibility.get("real_provider") is not True:
            errors.append("Compatibility Gate report is not from a real provider")
        if compatibility.get("provider") != "nebius_token_factory":
            errors.append("Compatibility Gate provider is not nebius_token_factory")

    rows = manifest.get("screenshots", []) if manifest else []
    if manifest:
        if manifest.get("evidence_class") != "final_competition":
            errors.append("screenshot evidence_class is not final_competition")
        if manifest.get("final_submission_eligible") is not True:
            errors.append("screenshot manifest is not final-submission eligible")
        if manifest.get("real_provider") is not True:
            errors.append("screenshot manifest is not marked as real-provider evidence")
        if manifest.get("provider") != "nebius_token_factory":
            errors.append("screenshot provider is not nebius_token_factory")
        receipt = manifest.get("live_provider_receipt", {})
        for field in ("model", "request_id", "trace_id"):
            if not isinstance(receipt.get(field), str) or not receipt[field].strip():
                errors.append(f"live_provider_receipt.{field} is missing")

    expected_paths = {
        (root / "evidence" / "screenshots" / name).relative_to(root).as_posix()
        for name in SCREENSHOT_FILES
    }
    actual_paths = {
        row.get("path") for row in rows if isinstance(row, dict) and row.get("path")
    }
    if len(rows) != len(SCREENSHOT_FILES) or actual_paths != expected_paths:
        errors.append("exactly the three required final screenshot paths are required")

    for row in rows:
        if not isinstance(row, dict):
            errors.append("screenshot row is not an object")
            continue
        relative = row.get("path", "")
        path = root / relative
        if not path.is_file():
            errors.append(f"screenshot file is missing: {relative}")
            continue
        content = path.read_bytes()
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            errors.append(f"screenshot is not a PNG: {relative}")
        if row.get("sha256") != hashlib.sha256(content).hexdigest():
            errors.append(f"screenshot hash mismatch: {relative}")
        if row.get("visible_scope_label") != FINAL_SCOPE_LABEL:
            errors.append(f"screenshot is not visibly labeled {FINAL_SCOPE_LABEL}: {relative}")
        if not str(row.get("visible_timestamp_text", "")).startswith("EVIDENCE UTC "):
            errors.append(f"visible UTC timestamp is missing: {relative}")
        if not _is_timezone_aware(row.get("captured_at_utc")):
            errors.append(f"capture timestamp is missing or timezone-naive: {relative}")

    result: dict[str, Any] = {
        "gate_version": "final-screenshot-gate-v1",
        "passed": not errors,
        "final_submission_eligible": not errors,
        "checked_screenshot_count": len(rows),
        "errors": sorted(set(errors)),
    }
    result["report_hash"] = canonical_hash(result)
    return result


def _read_json(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"{label} is missing: {path.as_posix()}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"{label} cannot be read: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return value


def _is_timezone_aware(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None
