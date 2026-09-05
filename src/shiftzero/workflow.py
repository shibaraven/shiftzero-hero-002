from __future__ import annotations

import uuid
from pathlib import Path
from time import perf_counter_ns

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
        run_started_ns = perf_counter_ns()
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

        snapshot, snapshot_ref = recorder.call_tool(
            kind="tool.get_operational_snapshot",
            tool_name=ToolName.GET_OPERATIONAL_SNAPSHOT,
            arguments={},
            operation=world.snapshot,
        )
        state.transition(MissionStatus.OBSERVED)
        recorder.record("workflow.transition", {"state": state.current})

        source, source_ref = recorder.call_tool(
            kind="tool.inspect_location",
            tool_name=ToolName.INSPECT_LOCATION,
            arguments={"id": intent.source, "snapshot_id": snapshot.snapshot_id},
            operation=lambda: world.inspect_location(intent.source, snapshot.snapshot_id),
        )
        destination, destination_ref = recorder.call_tool(
            kind="tool.inspect_location",
            tool_name=ToolName.INSPECT_LOCATION,
            arguments={"id": intent.destination, "snapshot_id": snapshot.snapshot_id},
            operation=lambda: world.inspect_location(intent.destination, snapshot.snapshot_id),
        )
        if not source.exists or not destination.exists:
            state.transition(MissionStatus.FAILED_SAFE)
            recorder.record("workflow.failed_safe", {"reason": "invalid location entity"})
            raise UnsafeProposal("source or destination is not present in the live snapshot")

        plan, plan_ref = recorder.call_tool(
            kind="tool.plan_transport",
            tool_name=ToolName.PLAN_TRANSPORT,
            arguments={"intent": intent, "snapshot_id": snapshot.snapshot_id},
            operation=lambda: planner.plan(intent=intent, snapshot=snapshot),
        )
        state.transition(MissionStatus.PLANNED)
        recorder.record("workflow.transition", {"state": state.current})

        evidence_refs = [snapshot_ref, source_ref, destination_ref, plan_ref]
        proposal_result, _ = recorder.call_tool(
            kind="tool.propose_transport",
            tool_name=ToolName.PROPOSE_TRANSPORT,
            arguments={
                "intent": intent,
                "snapshot_id": snapshot.snapshot_id,
                "route_version": plan.route_version,
                "evidence_refs": evidence_refs,
            },
            operation=lambda: self.provider.propose_transport(
                intent=intent,
                snapshot=snapshot,
                plan=plan,
                evidence_refs=evidence_refs,
            ),
        )
        proposal, proposal_call = proposal_result
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
        recorder.record(
            "tool.approve_transport",
            {
                "tool": ToolName.APPROVE_TRANSPORT,
                "arguments": {"proposal_id": proposal.proposal_id, "actor": approval_actor},
                "arguments_hash": canonical_hash(
                    {"proposal_id": proposal.proposal_id, "actor": approval_actor}
                ),
                "result": approval,
                "result_hash": canonical_hash(approval),
                "latency_ms": 0.0,
                "error": None,
            },
        )
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
            map_version=plan.map_version,
            snapshot_id=snapshot.snapshot_id,
            proof_hash=proof.proof_hash,
            status=MissionStatus.APPROVED,
            idempotency_key=f"dispatch:{proposal.proposal_hash}",
        )
        mission, _ = recorder.call_tool(
            kind="tool.start_mission",
            tool_name=ToolName.START_MISSION,
            arguments={
                "mission_id": mission.mission_id,
                "idempotency_key": mission.idempotency_key,
                "expected_status": MissionStatus.APPROVED,
            },
            operation=lambda: adapter.start(mission),
        )
        recorder.record("execution.started", mission)
        state.transition(MissionStatus.EXECUTING)
        recorder.record("workflow.transition", {"state": state.current})

        mission = adapter.advance(mission.mission_id)
        recorder.record("execution.telemetry", mission)
        obstacle = world.add_hero_blockage()
        recorder.record("sensor.aisle_blocked", obstacle)
        state.transition(MissionStatus.BLOCKED)
        recorder.record("workflow.transition", {"state": state.current})

        stop_latency_ms, _ = recorder.call_tool(
            kind="tool.stop_mission",
            tool_name=ToolName.STOP_MISSION,
            arguments={"mission_id": mission.mission_id, "trigger_source": obstacle.id},
            operation=lambda: adapter.local_stop(mission.mission_id, source=obstacle.id),
        )
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

        blocked_snapshot, _ = recorder.call_tool(
            kind="tool.get_operational_snapshot",
            tool_name=ToolName.GET_OPERATIONAL_SNAPSHOT,
            arguments={"reason": "blockage_recovery"},
            operation=world.snapshot,
        )
        recovery_result, _ = recorder.call_tool(
            kind="tool.propose_recovery",
            tool_name=ToolName.PROPOSE_RECOVERY,
            arguments={
                "mission_id": mission.mission_id,
                "goal_hash": intent.goal_hash,
                "blocked_node_id": obstacle.node_id,
                "snapshot_id": blocked_snapshot.snapshot_id,
            },
            operation=lambda: self.provider.recover_from_blockage(
                mission_id=mission.mission_id,
                goal_hash=intent.goal_hash,
                blocked_node_id=obstacle.node_id,
                snapshot=blocked_snapshot,
            ),
        )
        recovery, recovery_call = recovery_result
        model_calls.append(recovery_call)
        recorder.record("llm.recovery", recovery_call)
        recorder.record("recovery.intent", recovery)
        if recovery.action != "REPLAN" or recovery.preserve_goal_hash != intent.goal_hash:
            state.transition(MissionStatus.FAILED_SAFE)
            raise UnsafeProposal("recovery intent did not preserve the approved goal")
        state.transition(MissionStatus.REPLANNING)
        recorder.record("workflow.transition", {"state": state.current})
        current_node = world.agvs[mission.selected_agv].node_id
        replan, _ = recorder.call_tool(
            kind="tool.replan_mission",
            tool_name=ToolName.REPLAN_MISSION,
            arguments={
                "mission_id": mission.mission_id,
                "snapshot_id": blocked_snapshot.snapshot_id,
                "start_node": current_node,
                "force_agv": mission.selected_agv,
            },
            operation=lambda: planner.plan(
                intent=intent,
                snapshot=blocked_snapshot,
                start_node=current_node,
                force_agv=mission.selected_agv,
            ),
        )
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

        mission, _ = recorder.call_tool(
            kind="tool.resume_mission",
            tool_name=ToolName.RESUME_MISSION,
            arguments={
                "mission_id": mission.mission_id,
                "route_version": replan.route_version,
                "authorization": "equivalent-route-policy",
            },
            operation=lambda: adapter.replace_route(mission.mission_id, replan),
        )
        recorder.record("execution.resumed", mission)
        state.transition(MissionStatus.EXECUTING)
        recorder.record("workflow.transition", {"state": state.current})
        while mission.status == MissionStatus.EXECUTING:
            mission = adapter.advance(mission.mission_id)
            recorder.record("execution.telemetry", mission)
        state.transition(MissionStatus.COMPLETED)
        recorder.record("workflow.transition", {"state": state.current})
        total_duration_ms = round((perf_counter_ns() - run_started_ns) / 1_000_000, 6)
        final_agv = world.agvs[mission.selected_agv]
        if final_agv.pose is None:
            raise RuntimeError("completed mission is missing the final AGV pose")
        recorder.record(
            "outcome.completed",
            {
                "mission_id": mission.mission_id,
                "final_node": final_agv.node_id,
                "final_pose": final_agv.pose,
                "destination_occupancy": world.locations[intent.destination].occupancy,
                "trace_chain_valid": EvidenceRecorder.verify(recorder.path),
                "total_duration_ms": total_duration_ms,
                "human_interventions": 1,
                "estimated_model_cost_usd": sum(
                    call.estimated_cost_usd or 0 for call in model_calls
                ),
                "measurement_scope": "reference_simulator_fixture_provider"
                if self.provider.provider_name == "fixture"
                else "live_provider_reference_simulator",
            },
        )
        recorder.export_json()

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
