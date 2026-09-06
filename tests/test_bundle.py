from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from shiftzero.bundle import REQUIRED_PATHS, build_evidence_bundle
from shiftzero.domain import canonical_hash
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
    (tmp_path / "evidence/judge-mode-publication.json").write_text(
        json.dumps(
            {
                "access_mode": "public",
                "deployment_status": "succeeded",
                "http_authentication_used": False,
                "url": "https://example.invalid",
                "anonymous_http_checks": [{"status": 200}] * 4,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "evidence/public-repository.json").write_text(
        json.dumps(
            {
                "visibility": "public",
                "default_branch": "main",
                "repository_url": "https://github.com/example/project",
                "verified_commit": "a" * 40,
                "remote_head_at_verification": "a" * 40,
                "anonymous_http_checks": [{"status": 200}] * 2,
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
    live_summary = {
        "evidence_class": "live_provider_with_reference_simulator",
        "metadata": {
            "provider": "nebius_token_factory",
            "model": "nvidia/nemotron-3-super-120b-a12b",
            "prompt_contract": {"matches_tested_commit": True},
            "tool_schema": {"matches_tested_commit": True},
        },
        "compatibility": {"model_call_count": 0, "unique_request_id_count": 0},
        "measurements": {
            "replan_mission": {"sample_size": 0, "successful_result_count": 0},
            "cost_kpi": {
                "total_gate_estimated_usd": 1.0,
                "measurement_kind": "measured_tokens_x_captured_catalog_list_price_not_invoice",
            },
        },
    }
    live_summary["report_hash"] = canonical_hash(live_summary)
    (tmp_path / "evidence/live-runtime-summary.json").write_text(
        json.dumps(live_summary), encoding="utf-8"
    )
    serverless = {
        "artifact_ready": True,
        "cloud_deployed": False,
        "local_artifact": {"smoke_test_passed": True},
    }
    serverless["report_hash"] = canonical_hash(serverless)
    (tmp_path / "evidence/serverless-readiness.json").write_text(
        json.dumps(serverless), encoding="utf-8"
    )
    release_acceptance = {
        "passed_count": 8,
        "total_count": 12,
        "failed_ids": [],
        "blocked_external_ids": ["A06", "A07", "A11", "A12"],
    }
    release_acceptance["report_hash"] = canonical_hash(release_acceptance)
    (tmp_path / "evidence/release-acceptance.json").write_text(
        json.dumps(release_acceptance), encoding="utf-8"
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
    (tmp_path / "docs/A06_A07_FIELD_TEST_PROTOCOL.md").write_text(
        "agv.stationary_confirmed - sensor.filtered_obstacle <= 200 ms\n"
        "validate-physical-evidence\n"
        "Simulator exports use a\n"
        "different evidence class\n",
        encoding="utf-8",
    )
    (tmp_path / "apps/web/components/field-test-simulator.tsx").write_text(
        "SIMULATOR / PRE-PHYSICAL\n"
        "a06_physical_passed: false\n"
        "a07_physical_passed: false\n"
        "physical_evidence_required\n",
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
        assert embedded["bundle_version"] == "hero002-evidence-v9"
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
        assert embedded["completeness_checks"]["physical_field_test_harness_ready"] is True
        assert (
            embedded["completeness_checks"]["release_acceptance_has_only_external_blockers"]
            is True
        )
        assert embedded["completeness_checks"]["serverless_job_artifact_ready"] is True
        assert embedded["completeness_checks"]["serverless_cloud_deployed"] is False
        assert embedded["completeness_checks"]["judge_mode_public_and_anonymous"] is True
        assert embedded["completeness_checks"]["public_repository_ready"] is True
        assert embedded["completeness_checks"]["final_real_screenshots_ready"] is False
        assert embedded["completeness_checks"]["passed"] is False

    live = EvidenceRecorder(tmp_path / "evidence/runs/live-compatibility")
    _record_complete_hero_evidence(live, "M-LIVE")
    for kind, tool_name, request_id in (
        ("llm.intent", "parse_mission_intent", "request-intent"),
        ("llm.proposal", "propose_transport", "request-proposal"),
        ("llm.recovery", "propose_recovery", "request-recovery"),
    ):
        live.record(
            kind,
            {
                "provider": "nebius_token_factory",
                "model": "nvidia/nemotron-3-super-120b-a12b",
                "http_status": 200,
                "finish_reason": "tool_calls",
                "tool_name": tool_name,
                "request_id": request_id,
                "input_tokens": 100,
                "output_tokens": 50,
                "timed_out": False,
            },
        )
    live.export_json()
    live_gate = {
        "provider": "nebius_token_factory",
        "model": "nvidia/nemotron-3-super-120b-a12b",
        "real_provider": True,
        "official_gate_passed": True,
        "all_thresholds_passed": True,
        "failures": [],
        "metrics": {"requested_runs": 1, "completed_runs": 1},
    }
    live_gate["report_hash"] = canonical_hash(live_gate)
    (tmp_path / "evidence/compatibility/live-gate.json").write_text(
        json.dumps(live_gate), encoding="utf-8"
    )
    live_bundle = build_evidence_bundle(
        root=tmp_path,
        output_zip=tmp_path / "evidence/live.zip",
        manifest_path=tmp_path / "evidence/live-manifest.json",
    )
    assert live_bundle["official_gate_passed"] is True
    assert live_bundle["evidence_class"] == "live_provider_with_reference_simulator"
    assert live_bundle["completeness_checks"]["live_nebius_gate_passed"] is True
    assert live_bundle["completeness_checks"]["live_trace_count_matches_gate"] is True
    assert live_bundle["completeness_checks"]["live_provider_receipts_complete"] is True
    assert live_bundle["completeness_checks"]["live_request_ids_unique"] is True
    assert live_bundle["final_release_ready"] is False
