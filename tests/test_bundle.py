from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from shiftzero.bundle import REQUIRED_PATHS, build_evidence_bundle


def test_evidence_bundle_is_complete_and_reproducible(tmp_path: Path) -> None:
    for relative in REQUIRED_PATHS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {relative}\n", encoding="utf-8")
    trace = tmp_path / "evidence/sample-verified-run/TR-TEST/hero-run.jsonl"
    trace.parent.mkdir(parents=True)
    trace.write_text('{"trace":"valid"}\n', encoding="utf-8")

    first_zip = tmp_path / "evidence/first.zip"
    second_zip = tmp_path / "evidence/second.zip"
    first = build_evidence_bundle(
        root=tmp_path,
        output_zip=first_zip,
        manifest_path=tmp_path / "evidence/first-manifest.json",
    )
    second = build_evidence_bundle(
        root=tmp_path,
        output_zip=second_zip,
        manifest_path=tmp_path / "evidence/second-manifest.json",
    )

    assert first["bundle_sha256"] == second["bundle_sha256"]
    assert first_zip.read_bytes() == second_zip.read_bytes()
    assert first["official_gate_passed"] is False
    with ZipFile(first_zip) as archive:
        embedded = json.loads(archive.read("MANIFEST.json"))
        assert embedded["claim_scope"] == "reference_simulator_and_fixture_provider_only"
        assert len(embedded["files"]) == len(REQUIRED_PATHS) + 1
