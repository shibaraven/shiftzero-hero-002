import hashlib
import json
import struct
import zlib
from pathlib import Path

from shiftzero.screenshot_manifest import (
    FINAL_SCOPE_LABEL,
    SCREENSHOT_FILES,
    build_screenshot_manifest,
    validate_final_screenshot_manifest,
)


def _png(width: int, height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    return signature + struct.pack(">I", len(ihdr)) + chunk + struct.pack(">I", zlib.crc32(chunk))


def test_screenshot_manifest_hashes_pngs_and_binds_visible_timestamp(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    screenshots = evidence / "screenshots"
    screenshots.mkdir(parents=True)
    (evidence / "hero-summary.json").write_text(
        json.dumps({"evidence_captured_at": "2026-09-05T12:00:00+00:00"}),
        encoding="utf-8",
    )
    for name in SCREENSHOT_FILES:
        (screenshots / name).write_bytes(_png(1440, 900))

    report = build_screenshot_manifest(
        root=tmp_path,
        output_path=screenshots / "manifest.json",
    )

    assert len(report["screenshots"]) == 3
    assert all(row["width_px"] == 1440 for row in report["screenshots"])
    assert all(row["height_px"] == 900 for row in report["screenshots"])
    assert all(row["visible_scope_label"] == "MOCK / FIXTURE" for row in report["screenshots"])
    assert report["evidence_class"] == "preflight_fixture"
    assert report["final_submission_eligible"] is False
    assert report["replacement_required_after_live_gate"] is True
    assert all(
        "2026-09-05T12:00:00" in row["visible_timestamp_text"]
        for row in report["screenshots"]
    )
    assert (screenshots / "manifest.json").is_file()


def test_final_evidence_gate_rejects_fixture_manifest(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    screenshots = evidence / "screenshots"
    compatibility = evidence / "compatibility"
    screenshots.mkdir(parents=True)
    compatibility.mkdir(parents=True)
    (evidence / "hero-summary.json").write_text(
        json.dumps({"evidence_captured_at": "2026-09-05T12:00:00+00:00"}),
        encoding="utf-8",
    )
    for name in SCREENSHOT_FILES:
        (screenshots / name).write_bytes(_png(1440, 900))
    build_screenshot_manifest(root=tmp_path, output_path=screenshots / "manifest.json")
    (compatibility / "live-gate.json").write_text(
        json.dumps(
            {
                "official_gate_passed": False,
                "real_provider": False,
                "provider": "fixture",
            }
        ),
        encoding="utf-8",
    )

    result = validate_final_screenshot_manifest(
        root=tmp_path,
        manifest_path=screenshots / "manifest.json",
        compatibility_report_path=compatibility / "live-gate.json",
    )

    assert result["passed"] is False
    assert result["final_submission_eligible"] is False
    assert any("not final_competition" in error for error in result["errors"])
    assert any("not officially passed" in error for error in result["errors"])


def test_final_evidence_gate_accepts_live_receipts_and_exact_files(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    screenshots = evidence / "screenshots"
    compatibility = evidence / "compatibility"
    screenshots.mkdir(parents=True)
    compatibility.mkdir(parents=True)
    rows = []
    for name in SCREENSHOT_FILES:
        content = _png(1920, 1080)
        path = screenshots / name
        path.write_bytes(content)
        rows.append(
            {
                "path": path.relative_to(tmp_path).as_posix(),
                "sha256": hashlib.sha256(content).hexdigest(),
                "captured_at_utc": "2026-09-15T12:00:00+00:00",
                "visible_timestamp_text": "EVIDENCE UTC 2026-09-15T12:00:00+00:00",
                "visible_scope_label": FINAL_SCOPE_LABEL,
            }
        )
    (screenshots / "manifest.json").write_text(
        json.dumps(
            {
                "evidence_class": "final_competition",
                "final_submission_eligible": True,
                "provider": "nebius_token_factory",
                "real_provider": True,
                "live_provider_receipt": {
                    "model": "nvidia/example-model",
                    "request_id": "req-real-001",
                    "trace_id": "TR-REAL-001",
                },
                "screenshots": rows,
            }
        ),
        encoding="utf-8",
    )
    (compatibility / "live-gate.json").write_text(
        json.dumps(
            {
                "official_gate_passed": True,
                "real_provider": True,
                "provider": "nebius_token_factory",
            }
        ),
        encoding="utf-8",
    )

    result = validate_final_screenshot_manifest(
        root=tmp_path,
        manifest_path=screenshots / "manifest.json",
        compatibility_report_path=compatibility / "live-gate.json",
    )

    assert result["passed"] is True
    assert result["final_submission_eligible"] is True
    assert result["errors"] == []
