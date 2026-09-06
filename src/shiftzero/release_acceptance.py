from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from shiftzero.domain import canonical_hash


def _read_json(root: Path, relative: str) -> dict[str, object]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _optional_json(root: Path, relative: str) -> dict[str, object] | None:
    path = root / relative
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _hash_valid(report: dict[str, object] | None) -> bool:
    if not report:
        return False
    payload = dict(report)
    report_hash = payload.pop("report_hash", None)
    return report_hash == canonical_hash(payload)


def _item(
    acceptance_id: str,
    requirement: str,
    passed: bool,
    detail: str,
    evidence: list[str],
    *,
    external: bool = False,
) -> dict[str, object]:
    return {
        "id": acceptance_id,
        "requirement": requirement,
        "status": "passed" if passed else "external_evidence_required" if external else "failed",
        "passed": passed,
        "detail": detail,
        "evidence": evidence,
    }


def build_release_acceptance(*, root: Path, output_path: Path) -> dict[str, object]:
    """Build the A01-A12 acceptance ledger from checked-in evidence, without inference."""
    live_gate = _read_json(root, "evidence/compatibility/live-gate.json")
    live_runtime = _read_json(root, "evidence/live-runtime-summary.json")
    reliability = _read_json(root, "evidence/hero-reliability/report.json")
    scenarios = _read_json(root, "evidence/scenario-evaluation/metrics.json")
    judge_load = _read_json(root, "evidence/judge-mode-load.json")
    judge_publication = _read_json(root, "evidence/judge-mode-publication.json")
    public_repository = _read_json(root, "evidence/public-repository.json")
    baseline = _read_json(root, "evidence/baseline-comparison.json")
    impact = _read_json(root, "evidence/impact-load-model.json")
    physical = _optional_json(root, "evidence/physical/validation-report.json")
    final_video = _optional_json(root, "evidence/video/final-video-validation.json")
    devpost = _optional_json(root, "evidence/submission/devpost-validation.json")
    ui_source = (root / "apps/web/components/mission-console.tsx").read_text(
        encoding="utf-8"
    )

    compatibility = live_runtime.get("compatibility", {})
    live_model_calls = live_runtime.get("measurements", {}).get("model_calls", {})
    a01 = bool(
        _hash_valid(live_gate)
        and _hash_valid(live_runtime)
        and live_gate.get("official_gate_passed") is True
        and live_gate.get("real_provider") is True
        and compatibility.get("all_trace_chains_valid") is True
        and compatibility.get("model_call_count") == 360
        and compatibility.get("unique_request_id_count") == 360
        and live_model_calls.get("sample_size") == 360
    )
    a02 = bool(
        _hash_valid(live_gate)
        and live_gate.get("all_thresholds_passed") is True
        and live_gate.get("failures") == []
        and live_gate.get("metrics", {}).get("completed_runs") == 120
        and all(live_gate.get("thresholds_passed", {}).values())
    )
    a03 = bool(
        _hash_valid(reliability)
        and reliability.get("acceptance_passed") is True
        and reliability.get("max_consecutive_passes", 0) >= 20
        and reliability.get("passed_count", 0) >= 20
    )
    fault_controls = live_gate.get("fault_controls", {})
    a04 = bool(
        fault_controls.get("timeout_failed_closed") is True
        and fault_controls.get("http_429_bounded_retry") is True
        and fault_controls.get("duplicate_dispatch_idempotent") is True
        and fault_controls.get("duplicate_mission_count") == 0
        and fault_controls.get("wrong_entity_dispatch_count") == 0
        and fault_controls.get("stale_proposal_execution_count") == 0
    )
    a05 = bool(
        scenarios.get("sample_size") == 100
        and scenarios.get("validated_count") == 100
        and scenarios.get("safety_violation_count") == 0
        and scenarios.get("unsafe_plan_rejection_recall") == 1.0
    )
    a06 = bool(
        physical
        and _hash_valid(physical)
        and physical.get("evidence_class") == "physical_field_test"
        and physical.get("passed") is True
        and physical.get("a06_sensor_to_stop_passed") is True
        and physical.get("artifact_files_verified") == 4
    )
    a07 = bool(
        physical
        and _hash_valid(physical)
        and physical.get("evidence_class") == "physical_field_test"
        and physical.get("passed") is True
        and physical.get("a07_physical_loop_passed") is True
        and physical.get("artifact_files_verified") == 4
    )
    live_measurement = live_gate.get("metrics", {}).get("measurement", {})
    a08 = bool(
        scenarios.get("sample_size") == 100
        and scenarios.get("calculation_method")
        and reliability.get("measurement", {}).get("sample_size") == 20
        and reliability.get("measurement", {}).get("method")
        and live_measurement.get("sample_size") == 120
        and live_measurement.get("method")
        and live_model_calls.get("sample_size") == 360
        and judge_load.get("sample_count") == 20
        and judge_load.get("method")
        and baseline.get("sample_size_per_flow") == 20
        and baseline.get("method")
        and impact.get("inputs", {}).get("sample_days_per_load") == 20
        and impact.get("method")
        and impact.get("assumptions_are_not_measurements") is True
        and impact.get("official_or_physical_evidence") is False
    )
    main_entries = tuple(
        marker in ui_source
        for marker in (
            "{ id: 'mission', label: 'Run Hero' }",
            "{ id: 'architecture', label: 'Architecture' }",
            "{ id: 'evidence', label: 'Evidence' }",
            "{ id: 'source', label: 'GitHub' }",
        )
    )
    a09 = bool(
        judge_publication.get("access_mode") == "public"
        and judge_publication.get("deployment_status") == "succeeded"
        and judge_publication.get("http_authentication_used") is False
        and len(judge_publication.get("anonymous_http_checks", [])) >= 4
        and all(
            check.get("status") == 200
            for check in judge_publication.get("anonymous_http_checks", [])
        )
        and judge_load.get("acceptance_passed") is True
        and all(main_entries)
        and "setEvidenceError(true)" in ui_source
    )
    required_repository_paths = (
        "README.md",
        "LICENSE",
        "PRE_EXISTING_WORK.md",
        "SECURITY.md",
        "docker-compose.yml",
    )
    a10 = bool(
        public_repository.get("visibility") == "public"
        and public_repository.get("default_branch") == "main"
        and all((root / path).is_file() for path in required_repository_paths)
    )
    a11 = bool(
        final_video
        and _hash_valid(final_video)
        and final_video.get("evidence_class") == "final_physical_video"
        and final_video.get("passed") is True
        and final_video.get("duration_seconds", 180) < 180
        and final_video.get("continuous_physical_segment_seconds", 0) >= 65
        and final_video.get("minimum_vertical_resolution", 0) >= 1080
        and final_video.get("english_narration_or_subtitles") is True
        and final_video.get("anonymous_public_playback_verified") is True
    )
    a12 = bool(
        devpost
        and _hash_valid(devpost)
        and devpost.get("evidence_class") == "devpost_submission_validation"
        and devpost.get("passed") is True
        and devpost.get("submitted") is True
        and devpost.get("all_links_anonymous_verified") is True
        and devpost.get("submission_url")
    )

    items = [
        _item(
            "A01",
            "Live Nebius/Nemotron runtime trace is visible and verifiable",
            a01,
            "360 live, unique, hash-linked Token Factory tool-call receipts.",
            ["evidence/compatibility/live-gate.json", "evidence/live-runtime-summary.json"],
        ),
        _item(
            "A02",
            "Compatibility Gate: 120 runs and every hard threshold passes",
            a02,
            "120/120 runs; every declared threshold passes with no failures.",
            ["evidence/compatibility/live-gate.json"],
        ),
        _item(
            "A03",
            "HERO-002 succeeds end to end 20 consecutive times",
            a03,
            "20/20 independent reference-simulator runs pass with valid trace chains.",
            ["evidence/hero-reliability/report.json"],
        ),
        _item(
            "A04",
            "Timeout/429 retry creates no duplicate mission or wrong dispatch",
            a04,
            "Fault controls fail closed; duplicate and wrong-entity dispatch counts are zero.",
            ["evidence/compatibility/live-gate.json"],
        ),
        _item(
            "A05",
            "100 scenarios complete with zero safety violations",
            a05,
            "100/100 outcomes validated; 0 safety violations; unsafe recall 100%.",
            ["evidence/scenario-evaluation/metrics.json"],
        ),
        _item(
            "A06",
            "Physical local sensor-to-stop is at most 200 ms and cloud independent",
            a06,
            (
                "Correlated physical evidence passes the strict validator."
                if a06
                else (
                    "Needs onsite clocks, sensor/edge/AGV telemetry and "
                    "disconnected-cloud stop proof."
                )
            ),
            ["schemas/physical-field-evidence.schema.json", "docs/A06_A07_FIELD_TEST_PROTOCOL.md"],
            external=not a06,
        ),
        _item(
            "A07",
            "Physical AGV blockage, stop, replan and completion are all recorded",
            a07,
            (
                "One physical session passes the correlated full-loop validator."
                if a07
                else (
                    "Needs the original onsite video, telemetry, sensor and "
                    "MQTT/VDA5050 artifacts."
                )
            ),
            ["schemas/physical-field-evidence.schema.json", "docs/A06_A07_FIELD_TEST_PROTOCOL.md"],
            external=not a07,
        ),
        _item(
            "A08",
            "Every current claim has a sample count and measurement method",
            a08,
            (
                "Live, simulator, browser, baseline and projection claims retain "
                "scope and method labels."
            ),
            [
                "evidence/live-runtime-summary.json",
                "evidence/scenario-evaluation/metrics.json",
                "evidence/judge-mode-load.json",
                "evidence/baseline-comparison.json",
                "evidence/impact-load-model.json",
            ],
        ),
        _item(
            "A09",
            "Judge Mode has no login, runs in one click and explains errors",
            a09,
            (
                "Public anonymous checks pass; the four-entry Judge Mode has a "
                "bounded replay and error state."
            ),
            ["evidence/judge-mode-publication.json", "evidence/judge-mode-load.json"],
        ),
        _item(
            "A10",
            "Public repository, license, README and existing-work disclosure are complete",
            a10,
            "The repository is public and every mandatory top-level release file exists.",
            ["evidence/public-repository.json", "README.md", "PRE_EXISTING_WORK.md"],
        ),
        _item(
            "A11",
            "Video is under three minutes with 65 seconds physical and English narration/subtitles",
            a11,
            (
                "Final public video validation passes."
                if a11
                else "Needs the final 1080p onsite recording and public video URL."
            ),
            ["docs/VIDEO_SHOTLIST.md"],
            external=not a11,
        ),
        _item(
            "A12",
            "Every Devpost link is anonymously verified and the entry is submitted",
            a12,
            (
                "Submitted Devpost entry and anonymous link audit pass."
                if a12
                else (
                    "Needs the final video URL, Devpost submission URL and "
                    "owner-authorized submit action."
                )
            ),
            ["docs/DEVPOST_DRAFT.md", "docs/SUBMISSION_CHECKLIST.md"],
            external=not a12,
        ),
    ]
    passed_count = sum(item["passed"] is True for item in items)
    failed = [item["id"] for item in items if item["status"] == "failed"]
    blocked = [item["id"] for item in items if item["status"] == "external_evidence_required"]
    report: dict[str, object] = {
        "schema_version": "release-acceptance-v1",
        "spec_version": "HERO-002 competition spec v2.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "claim_boundary": (
            "Passed means the checked evidence satisfies that item. Simulator rehearsal never "
            "satisfies physical A06/A07, and draft assets never satisfy A11/A12."
        ),
        "passed_count": passed_count,
        "total_count": 12,
        "blocked_external_ids": blocked,
        "failed_ids": failed,
        "all_acceptance_passed": passed_count == 12,
        "items": items,
    }
    report["report_hash"] = canonical_hash(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report
