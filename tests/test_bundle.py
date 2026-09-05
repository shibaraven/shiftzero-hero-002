from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from shiftzero.bundle import REQUIRED_PATHS, build_evidence_bundle
from shiftzero.evidence import EvidenceRecorder


def test_evidence_bundle_is_complete_and_reproducible(tmp_path: Path) -> None:
    for relative in REQUIRED_PATHS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {relative}\n", encoding="utf-8")
    for name in (
        "01-completed.png",
        "02-model-tool-call.png",
        "03-verified-proof.png",
    ):
        (tmp_path / "evidence" / "screenshots" / name).write_bytes(
            b"\x89PNG\r\n\x1a\nfixture"
        )
    (tmp_path / "evidence/scenario-evaluation/metrics.json").write_text(
        json.dumps(
            {"sample_size": 100, "validated_count": 100, "safety_violation_count": 0}
        ),
        encoding="utf-8",
    )
    (tmp_path / "evidence/hero-reliability/report.json").write_text(
        json.dumps({"max_consecutive_passes": 20, "acceptance_passed": True}),
        encoding="utf-8",
    )
    sample = EvidenceRecorder(tmp_path / "evidence/sample-verified-run")
    sample.record("fixture", {"valid": True})
    sample.export_json()
    for index in range(20):
        recorder = EvidenceRecorder(tmp_path / "evidence/hero-reliability/runs")
        recorder.record("fixture", {"run": index})
        recorder.export_json()

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
        assert len(embedded["files"]) == len(REQUIRED_PATHS) + 42
        assert embedded["completeness_checks"]["scenario_all_outcomes_valid"] is True
        assert embedded["completeness_checks"]["passed"] is True
