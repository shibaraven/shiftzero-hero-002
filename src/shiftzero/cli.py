from __future__ import annotations

import argparse
import json
from pathlib import Path

from shiftzero.agent import FixtureProvider, TokenFactoryProvider
from shiftzero.bundle import build_evidence_bundle
from shiftzero.compatibility import run_compatibility_gate
from shiftzero.config import TokenFactorySettings
from shiftzero.evaluation import evaluate_scenarios
from shiftzero.schema_export import export_schemas
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

    bundle = subparsers.add_parser(
        "build-evidence-bundle", help="Create a reproducible offline evidence archive"
    )
    bundle.add_argument("--root", type=Path, default=Path.cwd())
    bundle.add_argument("--output", type=Path, default=Path("evidence/HERO002-evidence-bundle.zip"))
    bundle.add_argument("--manifest", type=Path, default=Path("evidence/bundle-manifest.json"))

    args = parser.parse_args()
    scenario = load_default_scenario()

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

    if args.command == "build-evidence-bundle":
        manifest = build_evidence_bundle(
            root=args.root.resolve(),
            output_zip=args.output.resolve(),
            manifest_path=args.manifest.resolve(),
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
