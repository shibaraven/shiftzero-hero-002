import json
import struct
import zlib
from pathlib import Path

from shiftzero.screenshot_manifest import SCREENSHOT_FILES, build_screenshot_manifest


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
    assert all(
        "2026-09-05T12:00:00" in row["visible_timestamp_text"]
        for row in report["screenshots"]
    )
    assert (screenshots / "manifest.json").is_file()
