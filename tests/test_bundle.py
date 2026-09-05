from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from shiftzero.bundle import REQUIRED_PATHS, build_evidence_bundle
from shiftzero.evidence import EvidenceRecorder

P0_TOOL_SPAN_KINDS = (
    "tool.get_operational_snapshot",
    "tool.inspect_location",
    "tool.plan_transport",
    "tool.propose_transport",
    "tool.approve_transport",
    "tool.get_mission_status",
    "tool.replan_mission",
    "tool.get_operation_metrics",
)


def _record_complete_hero_evidence(recorder: EvidenceRecorder, mission_id: str) -> None:
    for kind in P0_TOOL_SPAN_KINDS:
        tool_name = kind.removeprefix("tool.")
        recorder.call_tool(
            kind=kind,
            tool_name=tool_name,
            arguments={"mission_id": mission_id},
            operation=lambda name=tool_name: {"tool": name, "completed": True},
        )
    approval_check = {
        "name": "approval_integrity",
        "passed": True,
        "detail": "proposal hash, actor and expiry verified",
        "evidence_hash": "fixture-proof-hash",
    }
    recorder.record("safety.proof", {"checks": [approval_check]})
    recorder.record("safety.replan_proof", {"checks": [approval_check]})


def test_evidence_bundle_is_complete_and_reproducible(tmp_path: Path) -> None:
    for relative in REQUIRED_PATHS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {relative}\n", encoding="utf-8")
    screenshot_names = (
        "01-completed.png",
        "02-model-tool-call.png",
        "03-verified-proof.png",
    )
    screenshot_content = b"\x89PNG\r\n\x1a\nfixture"
    for name in screenshot_names:
        (tmp_path / "evidence" / "screenshots" / name).write_bytes(screenshot_content)
    (tmp_path / "evidence/screenshots/manifest.json").write_text(
        json.dumps(
            {
                "evidence_class": "preflight_fixture",
                "final_submission_eligible": False,
                "provider": "fixture",
                "real_provider": False,
                "replacement_required_after_live_gate": True,
                "screenshots": [
                    {
                        "path": f"evidence/screenshots/{name}",
                        "sha256": hashlib.sha256(screenshot_content).hexdigest(),
                        "visible_scope_label": "MOCK / FIXTURE",
                        "visible_timestamp_text": "EVIDENCE UTC 2026-09-05T12:00:00Z",
                    }
                    for name in screenshot_names
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "evidence/scenario-evaluation/metrics.json").write_text(
        json.dumps({"sample_size": 100, "validated_count": 100, "safety_violation_count": 0}),
        encoding="utf-8",
    )
    (tmp_path / "evidence/hero-reliability/report.json").write_text(
        json.dumps({"max_consecutive_passes": 20, "acceptance_passed": True}),
        encoding="utf-8",
    )
    (tmp_path / "evidence/judge-mode-load.json").write_text(
        json.dumps(
            {
                "acceptance_passed": True,
                "sample_count": 20,
                "p95_ms": 200,
                "threshold_ms": 5000,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "evidence/impact-load-model.json").write_text(
        json.dumps(
            {
                "loads": [
                    {"pallets_per_day": 400},
                    {"pallets_per_day": 450},
                    {"pallets_per_day": 500},
                ],
                "official_or_physical_evidence": False,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "THIRD_PARTY_LICENSES.json").write_text(
        json.dumps(
            {
                "summary": {
                    "total_packages": 1,
                    "missing_version": 0,
                    "missing_license": 0,
                    "missing_source": 0,
                },
                "packages": [
                    {
                        "name": "fixture",
                        "version": "1.0.0",
                        "license": "MIT",
                        "source": "https://example.invalid/fixture",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "docs/DEVPOST_DRAFT.md").write_text(
        "# Devpost\n\n## Existing work\n\nDeclared.\n", encoding="utf-8"
    )
    (tmp_path / "docs/VIDEO_SHOTLIST.md").write_text(
        "Encoded target: 2:58\n\nContinuous physical segment: 65 seconds\n",
        encoding="utf-8",
    )
    sample = EvidenceRecorder(tmp_path / "evidence/sample-verified-run")
    _record_complete_hero_evidence(sample, "M-SAMPLE")
    sample.export_json()
    for index in range(20):
        recorder = EvidenceRecorder(tmp_path / "evidence/hero-reliability/runs")
        _record_complete_hero_evidence(recorder, f"M-{index}")
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
        assert embedded["bundle_version"] == "hero002-preflight-evidence-v4"
        assert embedded["evidence_class"] == "preflight_fixture"
        assert embedded["claim_scope"] == "reference_simulator_and_fixture_provider_only"
        assert embedded["final_release_ready"] is False
        assert len(embedded["files"]) == len(REQUIRED_PATHS) + 42
        assert embedded["completeness_checks"]["scenario_all_outcomes_valid"] is True
        assert embedded["completeness_checks"]["third_party_inventory_complete"] is True
        assert (
            embedded["completeness_checks"]["typed_operation_metrics_for_every_trace"] is True
        )
        assert embedded["completeness_checks"]["p0_tool_spans_for_every_trace"] is True
        assert (
            embedded["completeness_checks"]["approval_integrity_in_every_safety_proof"]
            is True
        )
        assert (
            embedded["completeness_checks"]["approval_integrity_in_every_replan_proof"]
            is True
        )
        assert embedded["completeness_checks"]["devpost_has_existing_work_section"] is True
        assert (
            embedded["completeness_checks"]["video_plan_has_continuous_65_second_physical_segment"]
            is True
        )
        assert embedded["completeness_checks"]["local_preflight_passed"] is True
        assert embedded["completeness_checks"]["final_real_screenshots_ready"] is False
        assert embedded["completeness_checks"]["passed"] is False
