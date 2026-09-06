from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from shiftzero.domain import canonical_hash
from shiftzero.evidence import EvidenceRecorder

BUNDLE_VERSION = "hero002-evidence-v8"
LIVE_GATE_PATH = "evidence/compatibility/live-gate.json"
LIVE_TRACE_ROOT = "evidence/runs/live-compatibility"
LIVE_PROVIDER = "nebius_token_factory"
LIVE_MODEL = "nvidia/nemotron-3-super-120b-a12b"
LIVE_MODEL_TOOLS = frozenset(
    {"parse_mission_intent", "propose_transport", "propose_recovery"}
)
P0_TOOL_SPAN_KINDS = frozenset(
    {
        "tool.get_operational_snapshot",
        "tool.inspect_location",
        "tool.plan_transport",
        "tool.propose_transport",
        "tool.approve_transport",
        "tool.get_mission_status",
        "tool.replan_mission",
        "tool.get_operation_metrics",
    }
)
REQUIRED_PATHS = (
    "LICENSE",
    "Dockerfile.serverless",
    "PRE_EXISTING_WORK.md",
    "README.md",
    "THIRD_PARTY_LICENSES.json",
    "THIRD_PARTY_NOTICES.md",
    "requirements.lock",
    "evidence/scenario-evaluation/metrics.json",
    "evidence/scenario-evaluation/run-manifest.json",
    "evidence/scenario-evaluation/scenario-results.jsonl",
    "evidence/compatibility/preflight-report.json",
    "evidence/compatibility/token-factory-model-catalog.json",
    "evidence/live-runtime-summary.json",
    "evidence/hero-reliability/report.json",
    "evidence/hero-summary.json",
    "evidence/baseline-comparison.json",
    "evidence/impact-load-model.json",
    "evidence/judge-mode-load.json",
    "evidence/judge-mode-publication.json",
    "evidence/public-repository.json",
    "evidence/serverless-readiness.json",
    "evidence/screenshots/manifest.json",
    "evidence/METHODOLOGY.md",
    "evidence/screenshots/01-completed.png",
    "evidence/screenshots/02-model-tool-call.png",
    "evidence/screenshots/03-verified-proof.png",
    "scenarios/hero.json",
    "scenarios/evaluation_manifest.json",
    "schemas/safety-policy.json",
    "schemas/workflow-state-machine.json",
    "schemas/tool-catalog.json",
    "docs/SAFETY_RULES.md",
    "docs/IP_BOUNDARY.md",
    "docs/ARCHITECTURE.md",
    "docs/REAL_AGV_HANDOFF.md",
    "docs/SERVERLESS_JOB.md",
    "docs/SPEC_COMPLIANCE.md",
    "docs/AUTHORIZATION.md",
    "docs/JUDGE_MODE_PERFORMANCE.md",
    "docs/DEVPOST_DRAFT.md",
    "docs/FINAL_EVIDENCE_CAPTURE.md",
    "docs/VIDEO_SHOTLIST.md",
    "docs/A06_A07_FIELD_TEST_PROTOCOL.md",
    "schemas/openapi.json",
    "schemas/physical-field-evidence.schema.json",
    "apps/web/components/field-test-simulator.tsx",
)


def build_evidence_bundle(
    *,
    root: Path,
    output_zip: Path,
    manifest_path: Path,
) -> dict[str, object]:
    """Build a byte-reproducible, hash-indexed offline evidence bundle."""
    files = _resolve_files(root)
    entries = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path.read_bytes()),
        }
        for path in files
    ]
    completeness_checks = _completeness_checks(root, files)
    official_gate_passed = bool(
        completeness_checks["live_nebius_gate_passed"]
        and completeness_checks["live_trace_count_matches_gate"]
        and completeness_checks["live_provider_receipts_complete"]
        and completeness_checks["live_request_ids_unique"]
    )
    embedded_manifest: dict[str, object] = {
        "bundle_version": BUNDLE_VERSION,
        "evidence_class": (
            "live_provider_with_reference_simulator"
            if official_gate_passed
            else "preflight_fixture"
        ),
        "claim_scope": (
            "live_nebius_token_factory_with_reference_simulator_no_physical_hardware"
            if official_gate_passed
            else "reference_simulator_and_fixture_provider_only"
        ),
        "official_gate_passed": official_gate_passed,
        "final_release_ready": completeness_checks["passed"],
        "completeness_checks": completeness_checks,
        "files": entries,
    }
    manifest_bytes = (
        json.dumps(embedded_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        _write_reproducible(archive, "MANIFEST.json", manifest_bytes)
        for path in files:
            _write_reproducible(
                archive,
                path.relative_to(root).as_posix(),
                path.read_bytes(),
            )

    outer_manifest = {
        **embedded_manifest,
        "bundle_path": output_zip.relative_to(root).as_posix(),
        "bundle_bytes": output_zip.stat().st_size,
        "bundle_sha256": _sha256(output_zip.read_bytes()),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(outer_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return outer_manifest


def _resolve_files(root: Path) -> list[Path]:
    paths = [root / relative for relative in REQUIRED_PATHS]
    paths.extend(
        path for path in sorted((root / "schemas").glob("*.json")) if path not in paths
    )
    trace_paths = sorted((root / "evidence" / "sample-verified-run").glob("*/hero-run.jsonl"))
    paths.extend(trace_paths)
    trace_json_paths = sorted(
        (root / "evidence" / "sample-verified-run").glob("*/hero-run.json")
    )
    paths.extend(trace_json_paths)
    reliability_trace_paths = sorted(
        (root / "evidence" / "hero-reliability" / "runs").glob("*/hero-run.jsonl")
    )
    paths.extend(reliability_trace_paths)
    paths.extend(
        sorted((root / "evidence" / "hero-reliability" / "runs").glob("*/hero-run.json"))
    )
    scenario_trace_paths = sorted(
        (root / "evidence" / "scenario-evaluation" / "runs").glob("*/hero-run.jsonl")
    )
    paths.extend(scenario_trace_paths)
    paths.extend(
        sorted((root / "evidence" / "scenario-evaluation" / "runs").glob("*/hero-run.json"))
    )
    live_gate_path = root / LIVE_GATE_PATH
    if live_gate_path.is_file():
        paths.append(live_gate_path)
        paths.extend(
            sorted((root / LIVE_TRACE_ROOT).glob("*/hero-run.jsonl"))
        )
        paths.extend(
            sorted((root / LIVE_TRACE_ROOT).glob("*/hero-run.json"))
        )
    missing = [path for path in paths[: len(REQUIRED_PATHS)] if not path.is_file()]
    if missing:
        missing_text = ", ".join(path.relative_to(root).as_posix() for path in missing)
        raise FileNotFoundError(f"evidence bundle inputs are missing: {missing_text}")
    if not trace_paths:
        raise FileNotFoundError("evidence bundle needs a sample verified hero trace")
    if len(reliability_trace_paths) < 20:
        raise FileNotFoundError("evidence bundle needs at least 20 hero reliability traces")
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def _completeness_checks(root: Path, files: list[Path]) -> dict[str, object]:
    metrics = json.loads(
        (root / "evidence/scenario-evaluation/metrics.json").read_text(encoding="utf-8")
    )
    reliability = json.loads(
        (root / "evidence/hero-reliability/report.json").read_text(encoding="utf-8")
    )
    trace_paths = [path for path in files if path.name == "hero-run.jsonl"]
    trace_json_paths = [path for path in files if path.name == "hero-run.json"]
    screenshot_paths = [
        path for path in files if path.parent.name == "screenshots" and path.suffix == ".png"
    ]
    screenshot_manifest = json.loads(
        (root / "evidence/screenshots/manifest.json").read_text(encoding="utf-8")
    )
    screenshot_rows = {row["path"]: row for row in screenshot_manifest["screenshots"]}
    judge_load = json.loads(
        (root / "evidence/judge-mode-load.json").read_text(encoding="utf-8")
    )
    judge_publication = json.loads(
        (root / "evidence/judge-mode-publication.json").read_text(encoding="utf-8")
    )
    public_repository = json.loads(
        (root / "evidence/public-repository.json").read_text(encoding="utf-8")
    )
    impact_load = json.loads(
        (root / "evidence/impact-load-model.json").read_text(encoding="utf-8")
    )
    live_summary = json.loads(
        (root / "evidence/live-runtime-summary.json").read_text(encoding="utf-8")
    )
    serverless = json.loads(
        (root / "evidence/serverless-readiness.json").read_text(encoding="utf-8")
    )
    license_inventory = json.loads(
        (root / "THIRD_PARTY_LICENSES.json").read_text(encoding="utf-8")
    )
    devpost = (root / "docs/DEVPOST_DRAFT.md").read_text(encoding="utf-8")
    video_shotlist = (root / "docs/VIDEO_SHOTLIST.md").read_text(encoding="utf-8")
    physical_protocol = (root / "docs/A06_A07_FIELD_TEST_PROTOCOL.md").read_text(
        encoding="utf-8"
    )
    field_test_ui = (root / "apps/web/components/field-test-simulator.tsx").read_text(
        encoding="utf-8"
    )
    trace_events = {
        path: [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        for path in trace_paths
    }
    live_gate_path = root / LIVE_GATE_PATH
    live_gate = (
        json.loads(live_gate_path.read_text(encoding="utf-8"))
        if live_gate_path in files
        else None
    )
    live_trace_paths = [
        path
        for path in trace_paths
        if path.relative_to(root).as_posix().startswith(f"{LIVE_TRACE_ROOT}/")
    ]
    live_trace_json_paths = [
        path
        for path in trace_json_paths
        if path.relative_to(root).as_posix().startswith(f"{LIVE_TRACE_ROOT}/")
    ]
    live_model_events = [
        event
        for path in live_trace_paths
        for event in trace_events[path]
        if event["kind"] in {"llm.intent", "llm.proposal", "llm.recovery"}
    ]
    live_request_ids = [
        event["payload"].get("request_id") for event in live_model_events
    ]
    expected_live_runs = live_gate["metrics"]["requested_runs"] if live_gate else 0

    def live_receipt_complete(event: dict[str, object]) -> bool:
        payload = event["payload"]
        return bool(
            payload.get("provider") == LIVE_PROVIDER
            and payload.get("model") == LIVE_MODEL
            and payload.get("http_status") == 200
            and payload.get("finish_reason") == "tool_calls"
            and payload.get("tool_name") in LIVE_MODEL_TOOLS
            and payload.get("request_id")
            and isinstance(payload.get("input_tokens"), int)
            and payload["input_tokens"] > 0
            and isinstance(payload.get("output_tokens"), int)
            and payload["output_tokens"] > 0
            and payload.get("timed_out") is False
        )

    live_gate_hash_valid = False
    if live_gate:
        report_without_hash = dict(live_gate)
        report_hash = report_without_hash.pop("report_hash", None)
        live_gate_hash_valid = report_hash == canonical_hash(report_without_hash)

    live_summary_without_hash = dict(live_summary)
    live_summary_hash = live_summary_without_hash.pop("report_hash", None)
    live_summary_hash_valid = live_summary_hash == canonical_hash(live_summary_without_hash)
    serverless_without_hash = dict(serverless)
    serverless_hash = serverless_without_hash.pop("report_hash", None)
    serverless_hash_valid = serverless_hash == canonical_hash(serverless_without_hash)

    def proof_has_approval_integrity(events: list[dict[str, object]], kind: str) -> bool:
        return any(
            event["kind"] == kind
            and any(
                check.get("name") == "approval_integrity" and check.get("passed") is True
                for check in event["payload"]["checks"]
            )
            for event in events
        )

    checks: dict[str, object] = {
        "scenario_count_is_100": metrics["sample_size"] == 100,
        "scenario_all_outcomes_valid": metrics["validated_count"] == metrics["sample_size"],
        "scenario_safety_violations_zero": metrics["safety_violation_count"] == 0,
        "hero_twenty_consecutive_passes": reliability["max_consecutive_passes"] >= 20,
        "hero_acceptance_passed": reliability["acceptance_passed"] is True,
        "all_included_trace_chains_valid": all(
            EvidenceRecorder.verify(path) for path in trace_paths
        ),
        "typed_operation_metrics_for_every_trace": all(
            any(
                event["kind"] == "tool.get_operation_metrics"
                for event in trace_events[path]
            )
            for path in trace_paths
        ),
        "p0_tool_spans_for_every_trace": all(
            {event["kind"] for event in trace_events[path]} >= P0_TOOL_SPAN_KINDS
            for path in trace_paths
        ),
        "approval_integrity_in_every_safety_proof": all(
            proof_has_approval_integrity(trace_events[path], "safety.proof")
            for path in trace_paths
        ),
        "approval_integrity_in_every_replan_proof": all(
            proof_has_approval_integrity(trace_events[path], "safety.replan_proof")
            for path in trace_paths
        ),
        "structured_hero_json_for_every_trace": len(trace_json_paths) == len(trace_paths),
        "three_png_screenshots_present": len(screenshot_paths) >= 3
        and all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in screenshot_paths),
        "screenshots_have_capture_manifest": all(
            row is not None
            and row["sha256"] == _sha256(path.read_bytes())
            and row["visible_scope_label"] == "MOCK / FIXTURE"
            and row["visible_timestamp_text"].startswith("EVIDENCE UTC ")
            for path in screenshot_paths
            if (row := screenshot_rows.get(path.relative_to(root).as_posix())) is not None
        )
        and len(screenshot_rows) == len(screenshot_paths),
        "fixture_screenshots_are_preflight_only": (
            screenshot_manifest.get("evidence_class") == "preflight_fixture"
            and screenshot_manifest.get("final_submission_eligible") is False
            and screenshot_manifest.get("real_provider") is False
            and screenshot_manifest.get("replacement_required_after_live_gate") is True
        ),
        "final_real_screenshots_ready": (
            screenshot_manifest.get("evidence_class") == "final_competition"
            and screenshot_manifest.get("final_submission_eligible") is True
            and screenshot_manifest.get("real_provider") is True
            and screenshot_manifest.get("provider") == "nebius_token_factory"
            and all(
                row.get("visible_scope_label") == "LIVE / NEBIUS"
                for row in screenshot_manifest["screenshots"]
            )
        ),
        "live_nebius_gate_passed": bool(
            live_gate
            and live_gate.get("provider") == LIVE_PROVIDER
            and live_gate.get("model") == LIVE_MODEL
            and live_gate.get("real_provider") is True
            and live_gate.get("official_gate_passed") is True
            and live_gate.get("all_thresholds_passed") is True
            and live_gate.get("failures") == []
            and live_gate_hash_valid
        ),
        "live_trace_count_matches_gate": bool(
            live_gate
            and expected_live_runs > 0
            and len(live_trace_paths) == expected_live_runs
            and len(live_trace_json_paths) == expected_live_runs
            and live_gate["metrics"]["completed_runs"] == expected_live_runs
            and len(live_model_events) == expected_live_runs * len(LIVE_MODEL_TOOLS)
        ),
        "live_provider_receipts_complete": bool(
            live_model_events
            and all(live_receipt_complete(event) for event in live_model_events)
            and all(
                {
                    event["payload"].get("tool_name")
                    for event in trace_events[path]
                    if event["kind"] in {"llm.intent", "llm.proposal", "llm.recovery"}
                }
                == LIVE_MODEL_TOOLS
                for path in live_trace_paths
            )
        ),
        "live_request_ids_unique": bool(
            live_request_ids
            and all(isinstance(request_id, str) and request_id for request_id in live_request_ids)
            and len(live_request_ids) == len(set(live_request_ids))
        ),
        "live_runtime_metadata_complete": bool(
            live_summary_hash_valid
            and live_summary.get("evidence_class")
            == "live_provider_with_reference_simulator"
            and live_summary.get("metadata", {}).get("provider") == LIVE_PROVIDER
            and live_summary.get("metadata", {}).get("model") == LIVE_MODEL
            and live_summary.get("metadata", {})
            .get("prompt_contract", {})
            .get("matches_tested_commit")
            is True
            and live_summary.get("metadata", {})
            .get("tool_schema", {})
            .get("matches_tested_commit")
            is True
            and live_summary.get("compatibility", {}).get("model_call_count")
            == len(live_model_events)
            and live_summary.get("compatibility", {}).get("unique_request_id_count")
            == len(set(live_request_ids))
        ),
        "live_replan_and_cost_kpis_complete": bool(
            live_summary_hash_valid
            and live_summary.get("measurements", {})
            .get("replan_mission", {})
            .get("sample_size")
            == expected_live_runs
            and live_summary.get("measurements", {})
            .get("replan_mission", {})
            .get("successful_result_count")
            == expected_live_runs
            and live_summary.get("measurements", {})
            .get("cost_kpi", {})
            .get("total_gate_estimated_usd", 0)
            > 0
            and live_summary.get("measurements", {})
            .get("cost_kpi", {})
            .get("measurement_kind")
            == "measured_tokens_x_captured_catalog_list_price_not_invoice"
        ),
        "serverless_job_artifact_ready": bool(
            serverless_hash_valid
            and serverless.get("artifact_ready") is True
            and serverless.get("local_artifact", {}).get("smoke_test_passed") is True
        ),
        "serverless_cloud_deployed": bool(
            serverless_hash_valid and serverless.get("cloud_deployed") is True
        ),
        "live_trace_count": len(live_trace_paths),
        "live_model_call_count": len(live_model_events),
        "judge_mode_load_under_five_seconds": judge_load["acceptance_passed"] is True
        and judge_load["sample_count"] >= 20
        and judge_load["p95_ms"] < judge_load["threshold_ms"],
        "judge_mode_public_and_anonymous": bool(
            judge_publication.get("access_mode") == "public"
            and judge_publication.get("deployment_status") == "succeeded"
            and judge_publication.get("http_authentication_used") is False
            and judge_publication.get("url", "").startswith("https://")
            and len(judge_publication.get("anonymous_http_checks", [])) >= 4
            and all(
                row.get("status") == 200
                for row in judge_publication.get("anonymous_http_checks", [])
            )
        ),
        "public_repository_ready": bool(
            public_repository.get("visibility") == "public"
            and public_repository.get("default_branch") == "main"
            and public_repository.get("repository_url", "").startswith("https://github.com/")
            and len(public_repository.get("verified_commit", "")) == 40
            and public_repository.get("remote_head_at_verification")
            == public_repository.get("verified_commit")
            and len(public_repository.get("anonymous_http_checks", [])) >= 2
            and all(
                row.get("status") == 200
                for row in public_repository.get("anonymous_http_checks", [])
            )
        ),
        "impact_range_covers_400_to_500_pallets": {
            row["pallets_per_day"]
            for row in impact_load["loads"]
        }
        == {400, 450, 500}
        and impact_load["official_or_physical_evidence"] is False,
        "third_party_inventory_complete": all(
            license_inventory["summary"][key] == 0
            for key in ("missing_version", "missing_license", "missing_source")
        )
        and license_inventory["summary"]["total_packages"]
        == len(license_inventory["packages"]),
        "devpost_has_existing_work_section": "## Existing work" in devpost,
        "video_plan_has_continuous_65_second_physical_segment": (
            "Continuous physical segment: 65 seconds" in video_shotlist
            and "Encoded target: 2:58" in video_shotlist
        ),
        "physical_field_test_harness_ready": all(
            marker in physical_protocol
            for marker in (
                "agv.stationary_confirmed - sensor.filtered_obstacle <= 200 ms",
                "validate-physical-evidence",
                "Simulator exports use a",
                "different evidence class",
            )
        )
        and all(
            marker in field_test_ui
            for marker in (
                "SIMULATOR / PRE-PHYSICAL",
                "a06_physical_passed: false",
                "a07_physical_passed: false",
                "physical_evidence_required",
            )
        ),
        "required_file_count": len(files),
    }
    local_preflight_checks = (
        "scenario_count_is_100",
        "scenario_all_outcomes_valid",
        "scenario_safety_violations_zero",
        "hero_twenty_consecutive_passes",
        "hero_acceptance_passed",
        "all_included_trace_chains_valid",
        "typed_operation_metrics_for_every_trace",
        "p0_tool_spans_for_every_trace",
        "approval_integrity_in_every_safety_proof",
        "approval_integrity_in_every_replan_proof",
        "structured_hero_json_for_every_trace",
        "three_png_screenshots_present",
        "screenshots_have_capture_manifest",
        "fixture_screenshots_are_preflight_only",
        "judge_mode_load_under_five_seconds",
        "impact_range_covers_400_to_500_pallets",
        "third_party_inventory_complete",
        "devpost_has_existing_work_section",
        "video_plan_has_continuous_65_second_physical_segment",
        "physical_field_test_harness_ready",
        "serverless_job_artifact_ready",
        "judge_mode_public_and_anonymous",
        "public_repository_ready",
    )
    checks["local_preflight_passed"] = all(checks[name] is True for name in local_preflight_checks)
    checks["passed"] = (
        checks["local_preflight_passed"] is True
        and checks["live_nebius_gate_passed"] is True
        and checks["live_trace_count_matches_gate"] is True
        and checks["live_provider_receipts_complete"] is True
        and checks["live_request_ids_unique"] is True
        and checks["live_runtime_metadata_complete"] is True
        and checks["live_replan_and_cost_kpis_complete"] is True
        and checks["serverless_cloud_deployed"] is True
        and checks["final_real_screenshots_ready"] is True
    )
    return checks


def _write_reproducible(archive: ZipFile, name: str, content: bytes) -> None:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = (0o644 & 0xFFFF) << 16
    archive.writestr(info, content, compress_type=ZIP_DEFLATED, compresslevel=9)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
