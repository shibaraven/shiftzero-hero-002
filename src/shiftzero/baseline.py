from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

from shiftzero.adapters import SimulatorAdapter
from shiftzero.agent import FixtureProvider
from shiftzero.domain import ApprovalToken, Mission, MissionIntent, MissionStatus, canonical_hash
from shiftzero.evaluation import _git_commit, _source_tree_hash
from shiftzero.safety import SafetyEngine
from shiftzero.simulator import DeterministicPlanner, HeroScenario, ReferenceWorld
from shiftzero.workflow import WorkflowController


def run_fair_baseline(
    *, scenario: HeroScenario, output_path: Path, samples_per_flow: int = 20
) -> dict[str, Any]:
    if samples_per_flow < 20:
        raise ValueError("fair baseline requires at least 20 samples per flow")
    root = Path(__file__).resolve().parents[2]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    agent_rows: list[dict[str, Any]] = []
    manual_rows: list[dict[str, Any]] = []
    baseline_runs = output_path.parent / "baseline-agent-runs"
    for index in range(1, samples_per_flow + 1):
        started = time.perf_counter_ns()
        result = WorkflowController(
            scenario=scenario.model_copy(deep=True),
            provider=FixtureProvider(),
            evidence_root=baseline_runs,
        ).run_hero(approval_actor=f"baseline-agent-{index:03d}")
        agent_rows.append(
            {
                "sample": index,
                "completed": result.final_status == MissionStatus.COMPLETED,
                "duration_ms": round((time.perf_counter_ns() - started) / 1_000_000, 6),
                "human_interventions": 1,
                "trace_id": result.trace_id,
            }
        )
        manual_rows.append(_run_manual_flow(scenario, index))

    body: dict[str, Any] = {
        "baseline_version": "manual-vs-agent-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(root),
        "source_tree_hash": _source_tree_hash(root),
        "scenario_id": scenario.scenario_id,
        "same_conditions": True,
        "sample_size_per_flow": samples_per_flow,
        "measurement_scope": "in_process_reference_simulator_fixture_provider",
        "units": {
            "duration": "milliseconds",
            "failure_rate": "ratio_0_to_1",
            "human_interventions": "counted_operator_decisions",
        },
        "method": (
            "Both flows use the same map, AGV, pallet, destination, injected blockage and "
            "deterministic planner. Manual Flow explicitly performs inspect, approve, stop, "
            "replan and resume decisions; Agent Flow requires one approval."
        ),
        "manual_flow": _summarize(manual_rows),
        "agent_flow": _summarize(agent_rows),
        "claims_boundary": (
            "No labor or time savings claim is made from this in-process simulator baseline. "
            "Final claims require measured physical operations under matched conditions."
        ),
        "samples": {"manual": manual_rows, "agent": agent_rows},
    }
    body["report_hash"] = canonical_hash(body)
    output_path.write_text(
        json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return body


def _run_manual_flow(scenario: HeroScenario, sample: int) -> dict[str, Any]:
    started = time.perf_counter_ns()
    world = ReferenceWorld(scenario.model_copy(deep=True))
    planner = DeterministicPlanner()
    safety = SafetyEngine()
    adapter = SimulatorAdapter(world)
    intent = MissionIntent(
        pallet_id=scenario.expected.pallet_id,
        source=scenario.expected.source,
        destination=scenario.expected.destination,
        requested_agv=scenario.expected.selected_agv,
    )
    snapshot = world.snapshot()
    plan = planner.plan(intent=intent, snapshot=snapshot)
    proposal = FixtureProvider().propose_transport(
        intent=intent,
        snapshot=snapshot,
        plan=plan,
        evidence_refs=["manual:snapshot", "manual:inspection", "manual:plan"],
    )[0]
    proof = safety.verify(intent=intent, plan=plan, snapshot=snapshot, proposal=proposal)
    approval = ApprovalToken.issue(
        proposal_hash=proposal.proposal_hash,
        goal_hash=intent.goal_hash,
        actor=f"baseline-manual-{sample:03d}",
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
        snapshot_id=snapshot.snapshot_id,
        proof_hash=proof.proof_hash,
        status=MissionStatus.APPROVED,
        idempotency_key=f"baseline-manual:{proposal.proposal_hash}",
    )
    if not proof.passed or not approval.valid_for(proposal):
        raise RuntimeError("manual baseline setup failed deterministic verification")
    mission = adapter.start(mission)
    mission = adapter.advance(mission.mission_id)
    obstacle = world.add_hero_blockage()
    adapter.local_stop(mission.mission_id, obstacle.id)
    blocked_snapshot = world.snapshot()
    replan = planner.plan(
        intent=intent,
        snapshot=blocked_snapshot,
        start_node=world.agvs[mission.selected_agv].node_id,
        force_agv=mission.selected_agv,
    )
    replan_proof = safety.verify_replan(
        intent=intent,
        plan=replan,
        snapshot=blocked_snapshot,
        original_proposal=proposal,
    )
    if not replan_proof.passed:
        raise RuntimeError("manual baseline replan failed deterministic verification")
    mission = adapter.replace_route(mission.mission_id, replan)
    while mission.status == MissionStatus.EXECUTING:
        mission = adapter.advance(mission.mission_id)
    return {
        "sample": sample,
        "completed": mission.status == MissionStatus.COMPLETED,
        "duration_ms": round((time.perf_counter_ns() - started) / 1_000_000, 6),
        "human_interventions": 5,
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    durations = sorted(float(row["duration_ms"]) for row in rows)
    interventions = sorted(int(row["human_interventions"]) for row in rows)
    p95_index = max(0, min(len(durations) - 1, int((len(durations) - 1) * 0.95)))
    failures = sum(not bool(row["completed"]) for row in rows)
    return {
        "sample_size": len(rows),
        "duration_ms": {
            "median": round(median(durations), 6),
            "p95": round(durations[p95_index], 6),
        },
        "failure_count": failures,
        "failure_rate": failures / len(rows),
        "human_interventions": {
            "median": median(interventions),
            "p95": interventions[p95_index],
        },
    }
