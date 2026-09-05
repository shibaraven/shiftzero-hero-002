from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from shiftzero.evidence import EvidenceRecorder

BUNDLE_VERSION = "hero002-evidence-v2"
REQUIRED_PATHS = (
    "evidence/scenario-evaluation/metrics.json",
    "evidence/scenario-evaluation/run-manifest.json",
    "evidence/scenario-evaluation/scenario-results.jsonl",
    "evidence/compatibility/preflight-report.json",
    "evidence/hero-reliability/report.json",
    "evidence/hero-summary.json",
    "evidence/baseline-comparison.json",
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
    "schemas/openapi.json",
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
    embedded_manifest: dict[str, object] = {
        "bundle_version": BUNDLE_VERSION,
        "claim_scope": "reference_simulator_and_fixture_provider_only",
        "official_gate_passed": False,
        "completeness_checks": _completeness_checks(root, files),
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
    checks = {
        "scenario_count_is_100": metrics["sample_size"] == 100,
        "scenario_all_outcomes_valid": metrics["validated_count"] == metrics["sample_size"],
        "scenario_safety_violations_zero": metrics["safety_violation_count"] == 0,
        "hero_twenty_consecutive_passes": reliability["max_consecutive_passes"] >= 20,
        "hero_acceptance_passed": reliability["acceptance_passed"] is True,
        "all_included_trace_chains_valid": all(
            EvidenceRecorder.verify(path) for path in trace_paths
        ),
        "structured_hero_json_for_every_trace": len(trace_json_paths) == len(trace_paths),
        "three_png_screenshots_present": len(screenshot_paths) >= 3
        and all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in screenshot_paths),
        "required_file_count": len(files),
    }
    checks["passed"] = all(value is True for value in checks.values() if isinstance(value, bool))
    return checks


def _write_reproducible(archive: ZipFile, name: str, content: bytes) -> None:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = (0o644 & 0xFFFF) << 16
    archive.writestr(info, content, compress_type=ZIP_DEFLATED, compresslevel=9)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
