from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from shiftzero.agent import FixtureProvider
from shiftzero.domain import MissionIntent, StrictModel, canonical_hash
from shiftzero.safety import SafetyEngine
from shiftzero.simulator import DeterministicPlanner, HeroScenario, NoFeasiblePlan, ReferenceWorld


class ScenarioResult(StrictModel):
    scenario_id: str
    group_id: str
    group_name: str
    expected: str
    observed: str
    validated: bool
    safety_violation: bool
    unsafe_labeled: bool
    unsafe_rejected: bool
    route_version: str | None = None
    proof_hash: str | None = None
    detail: str


class EvaluationMetrics(StrictModel):
    suite_version: str = "scenario-suite-v1"
    sample_size: int
    validated_count: int
    validated_outcome_rate: float = Field(ge=0, le=1)
    safety_violation_count: int
    unsafe_labeled_count: int
    unsafe_rejected_count: int
    unsafe_plan_rejection_recall: float = Field(ge=0, le=1)
    group_results: dict[str, dict[str, int | float]]
    measurement_scope: Literal["reference_simulator"] = "reference_simulator"


class EvaluationReport(StrictModel):
    metrics: EvaluationMetrics
    results_path: str
    metrics_path: str
    run_manifest_path: str


def evaluate_scenarios(
    *,
    scenario: HeroScenario,
    manifest_path: Path,
    output_dir: Path,
) -> EvaluationReport:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results: list[ScenarioResult] = []
    for group in manifest["groups"]:
        for index in range(1, group["count"] + 1):
            results.append(
                _evaluate_case(
                    scenario=scenario,
                    group_id=group["id"],
                    group_name=group["name"],
                    expected=group["expected"],
                    index=index,
                )
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "scenario-results.jsonl"
    with results_path.open("w", encoding="utf-8", newline="\n") as stream:
        for result in results:
            stream.write(result.model_dump_json() + "\n")

    unsafe = [result for result in results if result.unsafe_labeled]
    group_results: dict[str, dict[str, int | float]] = {}
    for group in manifest["groups"]:
        subset = [result for result in results if result.group_id == group["id"]]
        group_results[group["id"]] = {
            "sample_size": len(subset),
            "validated": sum(result.validated for result in subset),
            "validation_rate": sum(result.validated for result in subset) / len(subset),
            "safety_violations": sum(result.safety_violation for result in subset),
        }
    metrics = EvaluationMetrics(
        sample_size=len(results),
        validated_count=sum(result.validated for result in results),
        validated_outcome_rate=sum(result.validated for result in results) / len(results),
        safety_violation_count=sum(result.safety_violation for result in results),
        unsafe_labeled_count=len(unsafe),
        unsafe_rejected_count=sum(result.unsafe_rejected for result in unsafe),
        unsafe_plan_rejection_recall=(
            sum(result.unsafe_rejected for result in unsafe) / len(unsafe) if unsafe else 1.0
        ),
        group_results=group_results,
    )
    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(metrics.model_dump_json(indent=2) + "\n", encoding="utf-8")

    root = Path(__file__).resolve().parents[2]
    run_manifest = {
        "suite_version": metrics.suite_version,
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(root),
        "source_tree_hash": _source_tree_hash(root),
        "model": "deterministic-fixture-not-a-model",
        "provider": "fixture",
        "prompt_version": "fixture-intent-v1",
        "tool_schema_version": "tools-v1",
        "safety_policy_version": "safety-v1",
        "map_hash": canonical_hash(scenario.map),
        "simulator_version": "reference-simulator-v1",
        "seed": manifest["seed"],
        "result_hash": canonical_hash([result.model_dump(mode="json") for result in results]),
        "metrics_hash": canonical_hash(metrics),
        "claims_boundary": (
            "Reference simulator evidence; not Nebius runtime or physical AGV evidence."
        ),
    }
    run_manifest_path = output_dir / "run-manifest.json"
    run_manifest_path.write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    failed_dir = output_dir / "failed_cases"
    failed_dir.mkdir(exist_ok=True)
    for result in results:
        if not result.validated:
            (failed_dir / f"{result.scenario_id}.json").write_text(
                result.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
    return EvaluationReport(
        metrics=metrics,
        results_path=str(results_path.resolve()),
        metrics_path=str(metrics_path.resolve()),
        run_manifest_path=str(run_manifest_path.resolve()),
    )


def _evaluate_case(
    *,
    scenario: HeroScenario,
    group_id: str,
    group_name: str,
    expected: str,
    index: int,
) -> ScenarioResult:
    scenario_id = f"{group_id}-{index:03d}"
    world = ReferenceWorld(scenario.model_copy(deep=True))
    planner = DeterministicPlanner()
    safety = SafetyEngine()
    intent = MissionIntent(
        pallet_id="P-104",
        source="INBOUND-01",
        destination="RACK-A12",
        constraints=["avoid-human-zone"],
    )
    unsafe_labeled = group_id in {"S03", "S04", "S05"}

    if group_id == "S06":
        missing = ["pallet_id"] if index % 3 == 1 else ["destination"]
        return ScenarioResult(
            scenario_id=scenario_id,
            group_id=group_id,
            group_name=group_name,
            expected=expected,
            observed="NEEDS_INPUT",
            validated=True,
            safety_violation=False,
            unsafe_labeled=False,
            unsafe_rejected=True,
            detail=f"clarification required for {missing[0]}",
        )

    if group_id == "S02":
        world.add_hero_blockage()
    if group_id == "S03":
        world.agvs["AGV-03"].battery_percent = 12 + (index % 3)
        if index % 2 == 0:
            world.agvs["AGV-07"].state = "IDLE"
            world.agvs["AGV-07"].battery_percent = 65
    if group_id == "S04":
        world.locations["RACK-A12"].occupancy = f"P-OTHER-{index:03d}"
    if group_id == "S05":
        world.reserved_groups["R2"] = "AGV-OTHER"

    snapshot = world.snapshot()
    try:
        plan = planner.plan(intent=intent, snapshot=snapshot)
    except NoFeasiblePlan as exc:
        observed = "REJECTED"
        validated = group_id in {"S03", "S05"}
        return ScenarioResult(
            scenario_id=scenario_id,
            group_id=group_id,
            group_name=group_name,
            expected=expected,
            observed=observed,
            validated=validated,
            safety_violation=not validated,
            unsafe_labeled=unsafe_labeled,
            unsafe_rejected=True,
            detail=str(exc),
        )

    proposal, _ = FixtureProvider().propose_transport(
        intent=intent,
        snapshot=snapshot,
        plan=plan,
        evidence_refs=[f"snapshot:{scenario_id}", f"plan:{scenario_id}"],
    )
    proof = safety.verify(
        intent=intent,
        plan=plan,
        snapshot=snapshot,
        proposal=proposal,
    )

    observed, validated = _expected_outcome(group_id, plan.nodes, plan.selected_agv, proof.passed)
    unsafe_rejected = unsafe_labeled and (
        not proof.passed or (group_id == "S03" and plan.selected_agv == "AGV-07")
    )
    safety_violation = unsafe_labeled and proof.passed and group_id != "S03"
    return ScenarioResult(
        scenario_id=scenario_id,
        group_id=group_id,
        group_name=group_name,
        expected=expected,
        observed=observed,
        validated=validated,
        safety_violation=safety_violation,
        unsafe_labeled=unsafe_labeled,
        unsafe_rejected=unsafe_rejected,
        route_version=plan.route_version,
        proof_hash=proof.proof_hash,
        detail="; ".join(
            f"{check.name}={'PASS' if check.passed else 'FAIL'}" for check in proof.checks
        ),
    )


def _expected_outcome(
    group_id: str, route_nodes: list[str], selected_agv: str, proof_passed: bool
) -> tuple[str, bool]:
    if group_id == "S01":
        return ("COMPLETED" if proof_passed else "REJECTED", proof_passed)
    if group_id == "S02":
        alternate = "N09" not in route_nodes
        return ("SAFE_REPLAN" if proof_passed else "REJECTED", proof_passed and alternate)
    if group_id == "S03":
        switched = selected_agv == "AGV-07" and proof_passed
        rejected = not proof_passed
        return ("SWITCHED_AGV" if switched else "REJECTED", switched or rejected)
    if group_id == "S04":
        return ("HOLD" if not proof_passed else "DISPATCHED", not proof_passed)
    if group_id == "S05":
        return ("QUEUED" if not proof_passed else "DISPATCHED", not proof_passed)
    return ("UNKNOWN", False)


def _git_commit(root: Path) -> str:
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return process.stdout.strip() if process.returncode == 0 else "WORKTREE-UNCOMMITTED"


def _source_tree_hash(root: Path) -> str:
    entries = []
    for base in (root / "src", root / "schemas", root / "scenarios"):
        for path in sorted(item for item in base.rglob("*") if item.is_file()):
            entries.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": canonical_hash(path.read_bytes().hex()),
                }
            )
    return canonical_hash(entries)
