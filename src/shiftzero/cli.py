from __future__ import annotations

import argparse
import json
from pathlib import Path

from shiftzero.agent import FixtureProvider, TokenFactoryProvider
from shiftzero.auth import AuthSettings, issue_access_token
from shiftzero.baseline import run_fair_baseline
from shiftzero.bundle import build_evidence_bundle
from shiftzero.compatibility import run_compatibility_gate
from shiftzero.config import TokenFactorySettings
from shiftzero.evaluation import evaluate_scenarios
from shiftzero.evidence_summary import build_hero_summary
from shiftzero.impact import run_impact_load_model
from shiftzero.license_inventory import build_license_inventory
from shiftzero.reliability import run_hero_reliability
from shiftzero.schema_export import export_schemas
from shiftzero.screenshot_manifest import (
    build_screenshot_manifest,
    validate_final_screenshot_manifest,
)
from shiftzero.simulator import load_default_scenario
from shiftzero.workflow import WorkflowController


def _provider(name: str) -> FixtureProvider | TokenFactoryProvider:
    if name == "fixture":
        return FixtureProvider()
    if name == "nebius":
        return TokenFactoryProvider(TokenFactorySettings.from_environment())
    raise ValueError(f"unknown provider: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="shiftzero")
    subparsers = parser.add_subparsers(dest="command", required=True)

    hero = subparsers.add_parser("hero", help="Run the complete blockage/replan hero scenario")
    hero.add_argument("--provider", choices=["fixture", "nebius"], default="fixture")
    hero.add_argument("--operator-text")
    hero.add_argument("--approval-actor", default="judge@example.invalid")
    hero.add_argument("--evidence-root", type=Path, default=Path("evidence/runs"))

    verify = subparsers.add_parser(
        "verify-token-factory", help="Make one real, forced Nemotron typed tool call"
    )
    verify.add_argument("--json", action="store_true")

    compatibility = subparsers.add_parser(
        "compatibility", help="Run the six-variant Compatibility Gate"
    )
    compatibility.add_argument("--provider", choices=["fixture", "nebius"], default="fixture")
    compatibility.add_argument("--repetitions", type=int, default=20)
    compatibility.add_argument("--evidence-root", type=Path, default=Path("evidence/runs"))
    compatibility.add_argument(
        "--report", type=Path, default=Path("evidence/compatibility/preflight-report.json")
    )

    schemas = subparsers.add_parser("export-schemas", help="Regenerate frozen JSON Schemas")
    schemas.add_argument("--output", type=Path, default=Path("schemas"))

    evaluation = subparsers.add_parser(
        "evaluate-scenarios", help="Run the deterministic 100-scenario suite"
    )
    evaluation.add_argument(
        "--manifest", type=Path, default=Path("scenarios/evaluation_manifest.json")
    )
    evaluation.add_argument("--output", type=Path, default=Path("evidence/scenario-evaluation"))

    reliability = subparsers.add_parser(
        "verify-hero-reliability", help="Run the complete fixture hero repeatedly"
    )
    reliability.add_argument("--runs", type=int, default=20)
    reliability.add_argument("--output", type=Path, default=Path("evidence/hero-reliability"))

    bundle = subparsers.add_parser(
        "build-evidence-bundle", help="Create a reproducible offline evidence archive"
    )
    bundle.add_argument("--root", type=Path, default=Path.cwd())
    bundle.add_argument("--output", type=Path, default=Path("evidence/HERO002-evidence-bundle.zip"))
    bundle.add_argument("--manifest", type=Path, default=Path("evidence/bundle-manifest.json"))

    summary = subparsers.add_parser(
        "build-hero-summary", help="Extract a judge-readable summary from verified evidence"
    )
    summary.add_argument("--root", type=Path, default=Path.cwd())
    summary.add_argument("--output", type=Path, default=Path("evidence/hero-summary.json"))

    auth_token = subparsers.add_parser(
        "issue-auth-token", help="Issue a short-lived signed Agent API bearer token"
    )
    auth_token.add_argument("--subject", required=True)
    auth_token.add_argument(
        "--role",
        required=True,
        choices=["operator", "approver", "executor", "safety", "viewer", "admin"],
    )
    auth_token.add_argument("--ttl-seconds", type=int, default=900)

    baseline = subparsers.add_parser(
        "fair-baseline", help="Measure matched Manual UI and Agent Flow simulator baselines"
    )
    baseline.add_argument("--samples", type=int, default=20)
    baseline.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/baseline-comparison.json"),
    )

    impact = subparsers.add_parser(
        "impact-load-model",
        help="Project the 400-500 pallets/day planning envelope without physical claims",
    )
    impact.add_argument("--sample-days", type=int, default=20)
    impact.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/impact-load-model.json"),
    )

    screenshot_manifest = subparsers.add_parser(
        "build-screenshot-manifest",
        help="Hash evidence screenshots and bind them to their visible UTC trace timestamp",
    )
    screenshot_manifest.add_argument("--root", type=Path, default=Path.cwd())
    screenshot_manifest.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/screenshots/manifest.json"),
    )

    final_evidence = subparsers.add_parser(
        "validate-final-evidence",
        help="Fail closed unless screenshots are backed by an official live Nebius gate",
    )
    final_evidence.add_argument("--root", type=Path, default=Path.cwd())
    final_evidence.add_argument(
        "--manifest",
        type=Path,
        default=Path("evidence/screenshots/manifest.json"),
    )
    final_evidence.add_argument(
        "--compatibility-report",
        type=Path,
        default=Path("evidence/compatibility/live-gate.json"),
    )

    licenses = subparsers.add_parser(
        "build-license-inventory",
        help="Freeze Python packages and inventory Python/npm licenses and sources",
    )
    licenses.add_argument("--root", type=Path, default=Path.cwd())
    licenses.add_argument(
        "--output", type=Path, default=Path("THIRD_PARTY_LICENSES.json")
    )
    licenses.add_argument(
        "--notices", type=Path, default=Path("THIRD_PARTY_NOTICES.md")
    )
    licenses.add_argument(
        "--requirements-lock", type=Path, default=Path("requirements.lock")
    )

    args = parser.parse_args()
    scenario = load_default_scenario()

    if args.command == "issue-auth-token":
        print(
            issue_access_token(
                subject=args.subject,
                role=args.role,
                settings=AuthSettings.from_environment(),
                ttl_seconds=args.ttl_seconds,
            )
        )
        return

    if args.command == "fair-baseline":
        report = run_fair_baseline(
            scenario=scenario,
            output_path=args.output,
            samples_per_flow=args.samples,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.command == "impact-load-model":
        report = run_impact_load_model(
            scenario=scenario,
            output_path=args.output,
            sample_days=args.sample_days,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.command == "build-screenshot-manifest":
        report = build_screenshot_manifest(
            root=args.root.resolve(),
            output_path=args.output.resolve(),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.command == "validate-final-evidence":
        report = validate_final_screenshot_manifest(
            root=args.root.resolve(),
            manifest_path=args.manifest.resolve(),
            compatibility_report_path=args.compatibility_report.resolve(),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        if not report["passed"]:
            raise SystemExit(2)
        return

    if args.command == "build-license-inventory":
        report = build_license_inventory(
            root=args.root,
            output_path=args.output,
            notices_path=args.notices,
            requirements_lock_path=args.requirements_lock,
        )
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.command == "hero":
        controller = WorkflowController(
            scenario=scenario,
            provider=_provider(args.provider),
            evidence_root=args.evidence_root,
        )
        result = controller.run_hero(
            operator_text=args.operator_text,
            approval_actor=args.approval_actor,
        )
        print(result.model_dump_json(indent=2))
        return

    if args.command == "verify-token-factory":
        provider = TokenFactoryProvider(TokenFactorySettings.from_environment())
        evidence = provider.verify_connectivity()
        message = (
            evidence.model_dump_json(indent=2) if args.json else "Token Factory tool call verified"
        )
        print(message)
        return

    if args.command == "compatibility":
        report = run_compatibility_gate(
            scenario=scenario,
            provider=_provider(args.provider),
            evidence_root=args.evidence_root,
            report_path=args.report,
            repetitions=args.repetitions,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.command == "export-schemas":
        for path in export_schemas(args.output):
            print(path)
        return

    if args.command == "evaluate-scenarios":
        report = evaluate_scenarios(
            scenario=scenario,
            manifest_path=args.manifest,
            output_dir=args.output,
        )
        print(report.model_dump_json(indent=2))
        return

    if args.command == "verify-hero-reliability":
        report = run_hero_reliability(
            scenario=scenario,
            output_dir=args.output,
            runs=args.runs,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.command == "build-evidence-bundle":
        manifest = build_evidence_bundle(
            root=args.root.resolve(),
            output_zip=args.output.resolve(),
            manifest_path=args.manifest.resolve(),
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.command == "build-hero-summary":
        result = build_hero_summary(root=args.root.resolve(), output_path=args.output.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
