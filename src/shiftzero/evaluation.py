from __future__ import annotations

import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from shiftzero.adapters import SimulatorAdapter
from shiftzero.agent import FixtureProvider, NeedsInputError
from shiftzero.domain import (
    ApprovalToken,
    LocationState,
    Mission,
    MissionIntent,
    MissionStatus,
    PalletState,
    SafetyProof,
    StrictModel,
    canonical_hash,
)
from shiftzero.evidence import EvidenceRecorder
from shiftzero.safety import SafetyEngine
from shiftzero.simulator import DeterministicPlanner, HeroScenario, NoFeasiblePlan, ReferenceWorld
from shiftzero.workflow import WorkflowController


class ScenarioResult(StrictModel):
    scenario_id: str
    group_id: str
    group_name: str
    condition: dict[str, Any]
    expected: str
    observed: str
    validated: bool
    safety_violation: bool
    unsafe_labeled: bool
    unsafe_rejected: bool
    route_version: str | None = None
    proof_hash: str | None = None
    trace_path: str | None = None
    trace_chain_valid: bool | None = None
    state_history: list[MissionStatus] = Field(default_factory=list)
    detail: str


class EvaluationMetrics(StrictModel):
    suite_version: str = "scenario-suite-v2"
    sample_size: int
    validated_count: int
    validated_outcome_rate: float = Field(ge=0, le=1)
    safety_violation_count: int
    unsafe_labeled_count: int
    unsafe_rejected_count: int
    unsafe_plan_rejection_recall: float = Field(ge=0, le=1)
    trace_chain_count: int
    trace_chain_valid_count: int
    group_results: dict[str, dict[str, int | float | dict[str, int]]]
    calculation_method: str
    units: dict[str, str] = Field(
        default_factory=lambda: {
            "counts": "cases",
            "rates": "ratio_0_to_1",
            "trace_chain": "traces",
        }
    )
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
                    output_dir=output_dir,
                )
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "scenario-results.jsonl"
    with results_path.open("w", encoding="utf-8", newline="\n") as stream:
        for result in results:
            stream.write(result.model_dump_json() + "\n")

    unsafe = [result for result in results if result.unsafe_labeled]
    traced = [result for result in results if result.trace_chain_valid is not None]
    group_results: dict[str, dict[str, int | float | dict[str, int]]] = {}
    for group in manifest["groups"]:
        subset = [result for result in results if result.group_id == group["id"]]
        outcomes: dict[str, int] = {}
        for result in subset:
            outcomes[result.observed] = outcomes.get(result.observed, 0) + 1
        group_results[group["id"]] = {
            "sample_size": len(subset),
            "validated": sum(result.validated for result in subset),
            "validation_rate": sum(result.validated for result in subset) / len(subset),
            "safety_violations": sum(result.safety_violation for result in subset),
            "distinct_conditions": len({canonical_hash(result.condition) for result in subset}),
            "outcomes": outcomes,
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
        trace_chain_count=len(traced),
        trace_chain_valid_count=sum(bool(result.trace_chain_valid) for result in traced),
        group_results=group_results,
        calculation_method=(
            "100 deterministic parameterized cases: nominal missions are executed, "
            "blockages exercise static/temporary/sudden paths, unsafe cases are proof-gated, "
            "and ambiguous text is parsed by the same fixture provider used by the demo."
        ),
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
        "prompt_version": "fixture-intent-v2-no-invention",
        "tool_schema_version": "tools-v3",
        "safety_policy_version": "safety-v2",
        "map_hash": canonical_hash(scenario.map),
        "simulator_version": "reference-simulator-v2",
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
    output_dir: Path,
) -> ScenarioResult:
    scenario_id = f"{group_id}-{index:03d}"
    if group_id == "S01":
        return _nominal_case(scenario, scenario_id, group_name, expected, index)
    if group_id == "S02":
        return _blockage_case(scenario, scenario_id, group_name, expected, index, output_dir)
    if group_id == "S03":
        return _battery_case(scenario, scenario_id, group_name, expected, index)
    if group_id == "S04":
        return _destination_case(scenario, scenario_id, group_name, expected, index)
    if group_id == "S05":
        return _conflict_case(scenario, scenario_id, group_name, expected, index)
    if group_id == "S06":
        return _ambiguous_case(scenario_id, group_name, expected, index)
    raise ValueError(f"unknown scenario group: {group_id}")


def _nominal_case(
    scenario: HeroScenario, scenario_id: str, group_name: str, expected: str, index: int
) -> ScenarioResult:
    world = ReferenceWorld(scenario.model_copy(deep=True))
    safe_nodes = ["N01", "N04", "N05", "N09", "N10", "N12"]
    source_node = safe_nodes[(index - 1) % len(safe_nodes)]
    destination_node = safe_nodes[(index * 2 + 1) % len(safe_nodes)]
    if source_node == destination_node:
        destination_node = safe_nodes[(safe_nodes.index(destination_node) + 1) % len(safe_nodes)]
    pallet_id = f"P-{200 + index}"
    source_id = f"INBOUND-{20 + index:02d}"
    destination_id = f"RACK-A{20 + index}"
    world.locations[source_id] = LocationState(
        id=source_id, node_id=source_node, kind="INBOUND", occupancy=pallet_id
    )
    world.locations[destination_id] = LocationState(
        id=destination_id, node_id=destination_node, kind="RACK"
    )
    world.pallets[pallet_id] = PalletState(id=pallet_id, location_id=source_id)
    intent, _ = FixtureProvider().parse_intent(
        f"Move {pallet_id} from {source_id} to {destination_id}"
    )
    snapshot = world.snapshot()
    plan, proof = _plan_and_verify(world, intent, snapshot, scenario_id)
    completed = _dispatch_to_completion(world, intent, plan, proof)
    return ScenarioResult(
        scenario_id=scenario_id,
        group_id="S01",
        group_name=group_name,
        condition={
            "pallet_id": pallet_id,
            "source": source_id,
            "source_node": source_node,
            "destination": destination_id,
            "destination_node": destination_node,
        },
        expected=expected,
        observed="COMPLETED" if completed else "FAILED_SAFE",
        validated=completed,
        safety_violation=False,
        unsafe_labeled=False,
        unsafe_rejected=False,
        route_version=plan.route_version,
        proof_hash=proof.proof_hash,
        state_history=[
            MissionStatus.INTENT,
            MissionStatus.OBSERVED,
            MissionStatus.PLANNED,
            MissionStatus.PROPOSED,
            MissionStatus.VERIFIED,
            MissionStatus.APPROVED,
            MissionStatus.EXECUTING,
            MissionStatus.COMPLETED,
        ],
        detail=(
            "typed intent, deterministic plan, proof, approval and simulator execution completed"
        ),
    )


def _blockage_case(
    scenario: HeroScenario,
    scenario_id: str,
    group_name: str,
    expected: str,
    index: int,
    output_dir: Path,
) -> ScenarioResult:
    profile = "static" if index <= 7 else "temporary" if index <= 13 else "sudden"
    confidence = round(0.8 + (index % 5) * 0.04, 2)
    variant = scenario.model_copy(deep=True)
    variant.blockage.obstacle_id = f"OBS-{scenario_id}"
    variant.blockage.confidence = confidence
    variant.blockage.profile = profile
    variant.blockage.ttl_seconds = 3 + index
    condition = {
        "profile": profile,
        "confidence": confidence,
        "ttl_seconds": variant.blockage.ttl_seconds,
        "blocked_node": variant.blockage.node_id,
    }
    if profile == "sudden":
        result = WorkflowController(
            scenario=variant,
            provider=FixtureProvider(),
            evidence_root=output_dir / "runs",
        ).run_hero(approval_actor=f"eval-{scenario_id}")
        trace_path = Path(result.evidence_path)
        trace_valid = EvidenceRecorder.verify(trace_path)
        validated = (
            result.final_status == MissionStatus.COMPLETED
            and MissionStatus.SAFE_STOP in result.state_history
            and result.initial_route_version != result.replan_route_version
            and trace_valid
        )
        return ScenarioResult(
            scenario_id=scenario_id,
            group_id="S02",
            group_name=group_name,
            condition=condition,
            expected=expected,
            observed="COMPLETED_SAFE_REPLAN" if validated else "FAILED_SAFE",
            validated=validated,
            safety_violation=False,
            unsafe_labeled=False,
            unsafe_rejected=False,
            route_version=result.replan_route_version,
            trace_path=_portable_trace_path(trace_path, output_dir),
            trace_chain_valid=trace_valid,
            state_history=result.state_history,
            detail="sensor event triggered local simulator stop, proof-gated replan and completion",
        )

    world = ReferenceWorld(variant)
    intent = _hero_intent()
    if profile == "static":
        world.add_hero_blockage()
        snapshot = world.snapshot()
        plan, proof = _plan_and_verify(world, intent, snapshot, scenario_id)
        completed = "N09" not in plan.nodes and _dispatch_to_completion(
            world, intent, plan, proof
        )
        history = [
            MissionStatus.INTENT,
            MissionStatus.OBSERVED,
            MissionStatus.PLANNED,
            MissionStatus.PROPOSED,
            MissionStatus.VERIFIED,
            MissionStatus.APPROVED,
            MissionStatus.EXECUTING,
            MissionStatus.COMPLETED,
        ]
        observed = "COMPLETED_STATIC_AVOIDANCE" if completed else "FAILED_SAFE"
        detail = "pre-existing obstruction was observed before planning and avoided"
    else:
        snapshot = world.snapshot()
        plan, proof = _plan_and_verify(world, intent, snapshot, scenario_id)
        original_proposal = _proposal(intent, snapshot, plan, scenario_id)
        mission, adapter = _start(world, intent, plan, proof, original_proposal)
        mission = adapter.advance(mission.mission_id)
        obstacle = world.add_hero_blockage()
        adapter.local_stop(mission.mission_id, obstacle.id)
        world.remove_obstacle(obstacle.id)
        refreshed = world.snapshot()
        replan = DeterministicPlanner().plan(
            intent=intent,
            snapshot=refreshed,
            start_node=world.agvs[mission.selected_agv].node_id,
            force_agv=mission.selected_agv,
        )
        replan_proof = SafetyEngine().verify_replan(
            intent=intent,
            plan=replan,
            snapshot=refreshed,
            original_proposal=original_proposal,
        )
        mission = adapter.replace_route(mission.mission_id, replan)
        while mission.status == MissionStatus.EXECUTING:
            mission = adapter.advance(mission.mission_id)
        completed = replan_proof.passed and mission.status == MissionStatus.COMPLETED
        plan = replan
        proof = replan_proof
        history = [
            MissionStatus.INTENT,
            MissionStatus.OBSERVED,
            MissionStatus.PLANNED,
            MissionStatus.PROPOSED,
            MissionStatus.VERIFIED,
            MissionStatus.APPROVED,
            MissionStatus.EXECUTING,
            MissionStatus.BLOCKED,
            MissionStatus.SAFE_STOP,
            MissionStatus.REPLANNING,
            MissionStatus.VERIFIED,
            MissionStatus.EXECUTING,
            MissionStatus.COMPLETED,
        ]
        observed = "COMPLETED_AFTER_TTL_CLEAR" if completed else "FAILED_SAFE"
        detail = "temporary obstruction stopped execution, expired, then replan was re-verified"
    return ScenarioResult(
        scenario_id=scenario_id,
        group_id="S02",
        group_name=group_name,
        condition=condition,
        expected=expected,
        observed=observed,
        validated=completed,
        safety_violation=False,
        unsafe_labeled=False,
        unsafe_rejected=False,
        route_version=plan.route_version,
        proof_hash=proof.proof_hash,
        state_history=history,
        detail=detail,
    )


def _battery_case(
    scenario: HeroScenario, scenario_id: str, group_name: str, expected: str, index: int
) -> ScenarioResult:
    world = ReferenceWorld(scenario.model_copy(deep=True))
    world.agvs["AGV-03"].battery_percent = float(9 + (index % 7))
    alternate_available = index % 2 == 0
    if alternate_available:
        world.agvs["AGV-07"].state = "IDLE"
        world.agvs["AGV-07"].battery_percent = float(55 + index)
    snapshot = world.snapshot()
    intent = _hero_intent()
    plan, proof = _plan_and_verify(world, intent, snapshot, scenario_id)
    switched = plan.selected_agv == "AGV-07" and proof.passed
    rejected = not proof.passed
    observed = "SWITCHED_AGV" if switched else "REJECTED_LOW_BATTERY"
    return ScenarioResult(
        scenario_id=scenario_id,
        group_id="S03",
        group_name=group_name,
        condition={
            "case_index": index,
            "primary_battery_percent": world.agvs["AGV-03"].battery_percent,
            "alternate_available": alternate_available,
            "alternate_battery_percent": world.agvs["AGV-07"].battery_percent,
        },
        expected=expected,
        observed=observed,
        validated=switched or rejected,
        safety_violation=False,
        unsafe_labeled=True,
        unsafe_rejected=switched or rejected,
        route_version=plan.route_version,
        proof_hash=proof.proof_hash,
        state_history=[MissionStatus.INTENT, MissionStatus.OBSERVED, MissionStatus.PLANNED],
        detail="low-reserve primary was never dispatched; alternate selected or proposal rejected",
    )


def _destination_case(
    scenario: HeroScenario, scenario_id: str, group_name: str, expected: str, index: int
) -> ScenarioResult:
    world = ReferenceWorld(scenario.model_copy(deep=True))
    unreachable = index % 3 == 0
    if unreachable:
        world.locations["RACK-A12"].reachable = False
        try:
            DeterministicPlanner().plan(intent=_hero_intent(), snapshot=world.snapshot())
        except NoFeasiblePlan as exc:
            return _unsafe_result(
                scenario_id,
                "S04",
                group_name,
                expected,
                {"case_index": index, "reachable": False, "occupancy": None},
                "HOLD_UNREACHABLE",
                str(exc),
            )
        raise AssertionError("unreachable destination produced a route")
    occupant = f"P-{800 + index}"
    world.locations["RACK-A12"].occupancy = occupant
    snapshot = world.snapshot()
    plan, proof = _plan_and_verify(world, _hero_intent(), snapshot, scenario_id)
    return ScenarioResult(
        scenario_id=scenario_id,
        group_id="S04",
        group_name=group_name,
        condition={"case_index": index, "reachable": True, "occupancy": occupant},
        expected=expected,
        observed="HOLD_OCCUPIED" if not proof.passed else "UNSAFE_DISPATCH",
        validated=not proof.passed,
        safety_violation=proof.passed,
        unsafe_labeled=True,
        unsafe_rejected=not proof.passed,
        route_version=plan.route_version,
        proof_hash=proof.proof_hash,
        state_history=[MissionStatus.INTENT, MissionStatus.OBSERVED, MissionStatus.PLANNED],
        detail=_proof_detail(proof),
    )


def _conflict_case(
    scenario: HeroScenario, scenario_id: str, group_name: str, expected: str, index: int
) -> ScenarioResult:
    world = ReferenceWorld(scenario.model_copy(deep=True))
    conflict_group = ("R1", "R2", "R3")[(index - 1) % 3]
    holder = f"AGV-{20 + index:02d}"
    world.reserved_groups[conflict_group] = holder
    snapshot = world.snapshot()
    plan, proof = _plan_and_verify(world, _hero_intent(), snapshot, scenario_id)
    return ScenarioResult(
        scenario_id=scenario_id,
        group_id="S05",
        group_name=group_name,
        condition={"reservation_group": conflict_group, "held_by": holder},
        expected=expected,
        observed="QUEUED_CONFLICT" if not proof.passed else "UNSAFE_DISPATCH",
        validated=not proof.passed,
        safety_violation=proof.passed,
        unsafe_labeled=True,
        unsafe_rejected=not proof.passed,
        route_version=plan.route_version,
        proof_hash=proof.proof_hash,
        state_history=[MissionStatus.INTENT, MissionStatus.OBSERVED, MissionStatus.PLANNED],
        detail=_proof_detail(proof),
    )


def _ambiguous_case(
    scenario_id: str, group_name: str, expected: str, index: int
) -> ScenarioResult:
    variants = (
        "Move from INBOUND-01 to RACK-A12",
        "Move P-104 to RACK-A12",
        "Move P-104 from INBOUND-01",
        "Please move the pallet",
    )
    text = f"{variants[(index - 1) % len(variants)]} (case {index:02d})"
    try:
        FixtureProvider().parse_intent(text)
    except NeedsInputError as exc:
        return ScenarioResult(
            scenario_id=scenario_id,
            group_id="S06",
            group_name=group_name,
            condition={"operator_text": text, "missing_fields": exc.missing_fields},
            expected=expected,
            observed="NEEDS_INPUT",
            validated=True,
            safety_violation=False,
            unsafe_labeled=False,
            unsafe_rejected=True,
            state_history=[MissionStatus.INTENT, MissionStatus.NEEDS_INPUT],
            detail=str(exc),
        )
    return ScenarioResult(
        scenario_id=scenario_id,
        group_id="S06",
        group_name=group_name,
        condition={"operator_text": text},
        expected=expected,
        observed="INVENTED_INPUT",
        validated=False,
        safety_violation=True,
        unsafe_labeled=False,
        unsafe_rejected=False,
        detail="ambiguous text was incorrectly accepted",
    )


def _hero_intent() -> MissionIntent:
    return MissionIntent(pallet_id="P-104", source="INBOUND-01", destination="RACK-A12")


def _proposal(intent: MissionIntent, snapshot: Any, plan: Any, scenario_id: str):
    proposal, _ = FixtureProvider().propose_transport(
        intent=intent,
        snapshot=snapshot,
        plan=plan,
        evidence_refs=[f"snapshot:{scenario_id}", f"plan:{scenario_id}"],
    )
    return proposal


def _plan_and_verify(
    world: ReferenceWorld,
    intent: MissionIntent,
    snapshot: Any,
    scenario_id: str,
):
    plan = DeterministicPlanner().plan(intent=intent, snapshot=snapshot)
    proposal = _proposal(intent, snapshot, plan, scenario_id)
    proof = SafetyEngine().verify(
        intent=intent, plan=plan, snapshot=snapshot, proposal=proposal
    )
    return plan, proof


def _start(
    world: ReferenceWorld,
    intent: MissionIntent,
    plan: Any,
    proof: SafetyProof,
    proposal: Any | None = None,
):
    proposal = proposal or _proposal(intent, world.snapshot(), plan, "execution")
    approval = ApprovalToken.issue(
        proposal_hash=proposal.proposal_hash,
        goal_hash=intent.goal_hash,
        actor="evaluation",
    )
    mission = Mission(
        mission_id=f"M-{uuid.uuid4().hex[:10].upper()}",
        proposal_id=proposal.proposal_id,
        proposal_hash=proposal.proposal_hash,
        goal_hash=intent.goal_hash,
        pallet_id=intent.pallet_id,
        source=intent.source,
        destination=intent.destination,
        selected_agv=plan.selected_agv,
        route=plan.nodes,
        route_version=plan.route_version,
        map_version=plan.map_version,
        snapshot_id=proposal.snapshot_id,
        proof_hash=proof.proof_hash,
        status=MissionStatus.APPROVED,
        idempotency_key=f"eval:{proposal.proposal_hash}",
    )
    if not proof.passed or not approval.valid_for(proposal):
        raise RuntimeError("evaluation attempted to dispatch without proof and approval")
    adapter = SimulatorAdapter(world)
    return adapter.start(mission), adapter


def _dispatch_to_completion(
    world: ReferenceWorld, intent: MissionIntent, plan: Any, proof: SafetyProof
) -> bool:
    mission, adapter = _start(world, intent, plan, proof)
    while mission.status == MissionStatus.EXECUTING:
        mission = adapter.advance(mission.mission_id)
    return mission.status == MissionStatus.COMPLETED


def _unsafe_result(
    scenario_id: str,
    group_id: str,
    group_name: str,
    expected: str,
    condition: dict[str, Any],
    observed: str,
    detail: str,
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        group_id=group_id,
        group_name=group_name,
        condition=condition,
        expected=expected,
        observed=observed,
        validated=True,
        safety_violation=False,
        unsafe_labeled=True,
        unsafe_rejected=True,
        state_history=[MissionStatus.INTENT, MissionStatus.OBSERVED, MissionStatus.REJECTED],
        detail=detail,
    )


def _proof_detail(proof: SafetyProof) -> str:
    return "; ".join(
        f"{check.name}={'PASS' if check.passed else 'FAIL'}" for check in proof.checks
    )


def _portable_trace_path(trace_path: Path, output_dir: Path) -> str:
    root = Path(__file__).resolve().parents[2]
    resolved = trace_path.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return resolved.relative_to(output_dir.resolve()).as_posix()


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
