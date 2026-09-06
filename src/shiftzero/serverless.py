from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shiftzero.domain import canonical_hash


def build_serverless_readiness(
    *, root: Path, output_path: Path, smoke_output: Path
) -> dict[str, Any]:
    """Record deployable-job readiness without confusing it with cloud deployment."""
    root = root.resolve()
    smoke_output = smoke_output.resolve()
    metrics_path = smoke_output / "metrics.json"
    manifest_path = smoke_output / "run-manifest.json"
    results_path = smoke_output / "scenario-results.jsonl"
    smoke_metrics = (
        json.loads(metrics_path.read_text(encoding="utf-8"))
        if metrics_path.is_file()
        else None
    )
    local_smoke_passed = bool(
        smoke_metrics
        and smoke_metrics.get("sample_size") == 100
        and smoke_metrics.get("validated_count") == 100
        and smoke_metrics.get("safety_violation_count") == 0
        and manifest_path.is_file()
        and results_path.is_file()
    )
    deployment_receipt_path = root / "evidence/serverless-deployment-receipt.json"
    cloud_receipt = (
        json.loads(deployment_receipt_path.read_text(encoding="utf-8"))
        if deployment_receipt_path.is_file()
        else None
    )
    cloud_deployed = bool(
        cloud_receipt
        and cloud_receipt.get("provider") == "nebius_serverless"
        and cloud_receipt.get("job_id")
        and cloud_receipt.get("status") == "SUCCEEDED"
        and cloud_receipt.get("output_manifest_sha256")
    )
    nebius_cli = shutil.which("nebius")
    docker_cli = shutil.which("docker")
    cli_config = Path.home() / ".nebius" / "config.yaml"
    project_id_present = bool(os.environ.get("NEBIUS_PROJECT_ID"))
    image_uri_present = bool(os.environ.get("NEBIUS_SERVERLESS_IMAGE_URI"))
    smoke_output_display = (
        smoke_output.relative_to(root).as_posix()
        if smoke_output.is_relative_to(root)
        else str(smoke_output)
    )
    blockers = []
    if not nebius_cli:
        blockers.append("Nebius CLI is not installed")
    if not cli_config.is_file():
        blockers.append("Nebius CLI profile/project configuration is absent")
    if not project_id_present:
        blockers.append("NEBIUS_PROJECT_ID is not configured")
    if not image_uri_present:
        blockers.append("NEBIUS_SERVERLESS_IMAGE_URI is not configured")
    if not docker_cli:
        blockers.append("A local container engine is not installed")
    if not cloud_deployed:
        blockers.append("No successful Nebius Serverless deployment receipt exists")

    report: dict[str, Any] = {
        "readiness_version": "nebius-serverless-v1",
        "checked_at": datetime.now(UTC).isoformat(),
        "job": {
            "dockerfile": "Dockerfile.serverless",
            "entrypoint": [
                "shiftzero",
                "evaluate-scenarios",
                "--manifest",
                "scenarios/evaluation_manifest.json",
                "--output",
                "/output",
            ],
            "expected_outputs": [
                "metrics.json",
                "run-manifest.json",
                "scenario-results.jsonl",
            ],
            "provider": "fixture",
            "network_or_api_key_required": False,
        },
        "local_artifact": {
            "dockerfile_present": (root / "Dockerfile.serverless").is_file(),
            "smoke_output": smoke_output_display,
            "smoke_test_passed": local_smoke_passed,
            "scenario_count": smoke_metrics.get("sample_size") if smoke_metrics else None,
            "validated_count": smoke_metrics.get("validated_count") if smoke_metrics else None,
            "safety_violation_count": (
                smoke_metrics.get("safety_violation_count") if smoke_metrics else None
            ),
        },
        "cloud_environment": {
            "nebius_cli_present": bool(nebius_cli),
            "nebius_cli_profile_present": cli_config.is_file(),
            "project_id_present": project_id_present,
            "container_engine_present": bool(docker_cli),
            "image_uri_present": image_uri_present,
        },
        "artifact_ready": bool(
            (root / "Dockerfile.serverless").is_file() and local_smoke_passed
        ),
        "cloud_deployed": cloud_deployed,
        "blockers": blockers,
        "claim_boundary": (
            "Container job artifact is locally smoke-tested; no Nebius cloud deployment is claimed."
        ),
    }
    report["report_hash"] = canonical_hash(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report
