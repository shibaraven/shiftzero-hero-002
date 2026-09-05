from __future__ import annotations

import uuid
from pathlib import Path

from shiftzero.adapters import SimulatorAdapter
from shiftzero.agent import IntentProposalProvider
from shiftzero.domain import (
    ApprovalToken,
    HeroRunResult,
    Mission,
    MissionStatus,
    ToolName,
    canonical_hash,
    utc_now,
)
from shiftzero.evidence import EvidenceRecorder
from shiftzero.safety import SafetyEngine
from shiftzero.simulator import DeterministicPlanner, HeroScenario, ReferenceWorld
from shiftzero.state_machine import WorkflowState


class UnsafeProposal(RuntimeError):
    pass


class WorkflowController:
    """Owns tool order, state transitions, validation, approval and side effects."""

    def __init__(
        self,
        *,
        scenario: HeroScenario,
        provider: IntentProposalProvider,
        evidence_root: Path,
    ) -> None:
        self.scenario = scenario
        self.provider = provider
        self.evidence_root = evidence_root

    def run_hero(
        self,
        *,
        operator_text: str | None = None,
        approval_actor: str = "judge@example.invalid",
    ) -> HeroRunResult:
        recorder = EvidenceRecorder(self.evidence_root)
        state = WorkflowState()
        world = ReferenceWorld(self.scenario.model_copy(deep=True))
        adapter = SimulatorAdapter(world)
        planner = DeterministicPlanner()
        safety = SafetyEngine()
        model_calls = []
        text = operator_text or self.scenario.operator_text
        recorder.record(
            "intent.received",
            {"operator_text": text, "operator_id": approval_actor, "state": state.current},
        )

        intent, intent_call = self.provider.parse_intent(text)
        model_calls.append(intent_call)
        recorder.record("llm.intent", intent_call)
        recorder.record("intent.typed", intent)

        snapshot = world.snapshot()
        snapshot_ref = recorder.record(
            "tool.get_operational_snapshot",
            {
                "tool": ToolName.GET_OPERATIONAL_SNAPSHOT,
                "arguments_hash": canonical_hash({}),
                "result": snapshot,
            },
        )
        state.transition(MissionStatus.OBSERVED)
        recorder.record("workflow.transition", {"state": state.current})

        source = world.inspect_location(intent.source, snapshot.snapshot_id)
        destination = world.inspect_location(intent.destination, snapshot.snapshot_id)
        source_ref = recorder.record(
            "tool.inspect_location",
            {
                "tool": ToolName.INSPECT_LOCATION,
                "arguments": {"id": intent.source},
                "result": source,
            },
        )
        destination_ref = recorder.record(
            "tool.inspect_location",
            {
                "tool": ToolName.INSPECT_LOCATION,
                "arguments": {"id": intent.destination},
                "result": destination,
            },
        )
        if not source.exists or not destination.exists:
            state.transition(MissionStatus.FAILED_SAFE)
            recorder.record("workflow.failed_safe", {"reason": "invalid location entity"})
            raise UnsafeProposal("source or destination is not present in the live snapshot")

        plan = planner.plan(intent=intent, snapshot=snapshot)
        plan_ref = recorder.record(
            "tool.plan_transport",
            {
                "tool": ToolName.PLAN_TRANSPORT,
                "arguments": intent,
                "result": plan,
            },
        )
        state.transition(MissionStatus.PLANNED)
        recorder.record("workflow.transition", {"state": state.current})

        evidence_refs = [snapshot_ref, source_ref, destination_ref, plan_ref]
        proposal, proposal_call = self.provider.propose_transport(
            intent=intent,
            snapshot=snapshot,
            plan=plan,
            evidence_refs=evidence_refs,
        )
        model_calls.append(proposal_call)
        recorder.record("llm.proposal", proposal_call)
        recorder.record("proposal.created", proposal)
        state.transition(MissionStatus.PROPOSED)
        recorder.record("workflow.transition", {"state": state.current})

        proof = safety.verify(
            intent=intent,
            plan=plan,
            snapshot=snapshot,
            proposal=proposal,
        )
        recorder.record("safety.proof", proof)
        if not proof.passed:
            state.transition(MissionStatus.REJECTED)
            recorder.record("workflow.rejected", {"proof_id": proof.proof_id})
            raise UnsafeProposal("deterministic safety proof failed")
        state.transition(MissionStatus.VERIFIED)
        recorder.record("workflow.transition", {"state": state.current})

        approval = ApprovalToken.issue(
            proposal_hash=proposal.proposal_hash,
            goal_hash=intent.goal_hash,
            actor=approval_actor,
        )
        if not approval.valid_for(proposal):
            state.transition(MissionStatus.REJECTED)
            raise UnsafeProposal("approval integrity validation failed")
        recorder.record("approval.granted", approval)
        state.transition(MissionStatus.APPROVED)
        recorder.record("workflow.transition", {"state": state.current})

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
            status=MissionStatus.APPROVED,
            idempotency_key=f"dispatch:{proposal.proposal_hash}",
        )
        mission = adapter.start(mission)
        recorder.record("execution.started", mission)
        state.transition(MissionStatus.EXECUTING)
        recorder.record("workflow.transition", {"state": state.current})

        mission = adapter.advance(mission.mission_id)
        recorder.record("execution.telemetry", mission)
        obstacle = world.add_hero_blockage()
        recorder.record("sensor.aisle_blocked", obstacle)
        state.transition(MissionStatus.BLOCKED)
        recorder.record("workflow.transition", {"state": state.current})

        stop_latency_ms = adapter.local_stop(mission.mission_id, source=obstacle.id)
        recorder.record(
            "execution.local_stop",
            {
                "mission_id": mission.mission_id,
                "trigger_source": obstacle.id,
                "latency_ms": stop_latency_ms,
                "measurement_kind": "simulated_process",
            },
        )
        state.transition(MissionStatus.SAFE_STOP)
        recorder.record("workflow.transition", {"state": state.current})

        blocked_snapshot = world.snapshot()
        state.transition(MissionStatus.REPLANNING)
        recorder.record("workflow.transition", {"state": state.current})
        current_node = world.agvs[mission.selected_agv].node_id
        replan = planner.plan(
            intent=intent,
            snapshot=blocked_snapshot,
            start_node=current_node,
            force_agv=mission.selected_agv,
        )
        recorder.record("tool.replan_mission", replan)
        replan_proof = safety.verify_replan(
            intent=intent,
            plan=replan,
            snapshot=blocked_snapshot,
            original_proposal=proposal,
        )
        recorder.record("safety.replan_proof", replan_proof)
        if not replan_proof.passed:
            state.transition(MissionStatus.FAILED_SAFE)
            raise UnsafeProposal("replan safety proof failed")
        if approval.goal_hash != intent.goal_hash or not (
            approval.issued_at <= utc_now() < approval.expires_at
        ):
            state.transition(MissionStatus.FAILED_SAFE)
            raise UnsafeProposal("replan changed or outlived the approved mission goal")
        state.transition(MissionStatus.VERIFIED)
        recorder.record(
            "workflow.transition",
            {"state": state.current, "authorization": "equivalent-route-policy"},
        )

        mission = adapter.replace_route(mission.mission_id, replan)
        recorder.record("execution.resumed", mission)
        state.transition(MissionStatus.EXECUTING)
        recorder.record("workflow.transition", {"state": state.current})
        while mission.status == MissionStatus.EXECUTING:
            mission = adapter.advance(mission.mission_id)
            recorder.record("execution.telemetry", mission)
        state.transition(MissionStatus.COMPLETED)
        recorder.record("workflow.transition", {"state": state.current})
        recorder.record(
            "outcome.completed",
            {
                "mission_id": mission.mission_id,
                "final_node": world.agvs[mission.selected_agv].node_id,
                "destination_occupancy": world.locations[intent.destination].occupancy,
                "trace_chain_valid": EvidenceRecorder.verify(recorder.path),
            },
        )

        return HeroRunResult(
            trace_id=recorder.trace_id,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            proposal_id=proposal.proposal_id,
            mission_id=mission.mission_id,
            initial_route_version=plan.route_version,
            replan_route_version=replan.route_version,
            final_status=mission.status,
            stop_latency_ms=round(stop_latency_ms, 6),
            stop_latency_kind="simulated_process",
            evidence_path=str(recorder.path.resolve()),
            state_history=state.history,
            model_calls=model_calls,
        )
