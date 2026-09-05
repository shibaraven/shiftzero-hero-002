from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

from shiftzero.adapters import SimulatorAdapter
from shiftzero.agent import IntentProposalProvider
from shiftzero.domain import (
    ApprovalToken,
    Mission,
    MissionIntent,
    MissionStatus,
    OperationalSnapshot,
    RecoveryIntent,
    RoutePlan,
    SafetyProof,
    TransportProposal,
    canonical_hash,
    utc_now,
)
from shiftzero.evidence import EvidenceRecorder
from shiftzero.safety import SafetyEngine
from shiftzero.simulator import DeterministicPlanner, HeroScenario, ReferenceWorld
from shiftzero.state_machine import WorkflowState


class MissionServiceError(RuntimeError):
    pass


class MissionConflictError(MissionServiceError):
    pass


class MissionPermissionError(MissionServiceError):
    pass


@dataclass
class MissionSession:
    session_id: str
    provider: IntentProposalProvider
    world: ReferenceWorld
    adapter: SimulatorAdapter
    recorder: EvidenceRecorder
    state: WorkflowState
    intent: MissionIntent
    snapshot: OperationalSnapshot | None = None
    plan: RoutePlan | None = None
    proposal: TransportProposal | None = None
    proof: SafetyProof | None = None
    approval: ApprovalToken | None = None
    mission: Mission | None = None
    replan: RoutePlan | None = None
    stop_latency_ms: float | None = None
    version: int = 1
    rejection_reason: str | None = None
    recovery: RecoveryIntent | None = None
    replan_proof: SafetyProof | None = None
    created_at: datetime = field(default_factory=utc_now)


class MissionService:
    def __init__(self, *, scenario: HeroScenario, evidence_root: Path) -> None:
        self.scenario = scenario
        self.evidence_root = evidence_root
        self._sessions: dict[str, MissionSession] = {}
        self._proposal_index: dict[str, str] = {}
        self._mission_index: dict[str, str] = {}
        self._trace_index: dict[str, str] = {}
        self._operations: dict[str, tuple[str, str]] = {}
        self._pending_operations: dict[str, tuple[str, str]] = {}
        self._lock = RLock()

    def create_intent(
        self,
        *,
        operator_text: str,
        operator_id: str,
        provider: IntentProposalProvider,
    ) -> MissionSession:
        with self._lock:
            recorder = EvidenceRecorder(self.evidence_root)
            intent, call = provider.parse_intent(operator_text)
            recorder.record(
                "intent.received",
                {"operator_text": operator_text, "operator_id": operator_id},
            )
            recorder.record("llm.intent", call)
            recorder.record("intent.typed", intent)
            world = ReferenceWorld(self.scenario.model_copy(deep=True))
            session = MissionSession(
                session_id=f"INT-{uuid.uuid4().hex[:10].upper()}",
                provider=provider,
                world=world,
                adapter=SimulatorAdapter(world),
                recorder=recorder,
                state=WorkflowState(),
                intent=intent,
            )
            self._sessions[session.session_id] = session
            self._trace_index[recorder.trace_id] = session.session_id
            return session

    def prepare_proposal(
        self,
        session_id: str,
        *,
        idempotency_key: str,
        expected_version: int,
    ) -> MissionSession:
        with self._lock:
            session = self._session(session_id)
            operation = self._begin_operation(
                session,
                name="prepare",
                idempotency_key=idempotency_key,
                expected_version=expected_version,
                payload={"session_id": session_id},
            )
            if operation is not None:
                return operation
            if session.state.current != MissionStatus.INTENT:
                raise MissionServiceError("proposal preparation requires INTENT state")
            snapshot, snapshot_ref = session.recorder.call_tool(
                kind="tool.get_operational_snapshot",
                tool_name="get_operational_snapshot",
                arguments={},
                operation=session.world.snapshot,
            )
            session.snapshot = snapshot
            session.state.transition(MissionStatus.OBSERVED)
            session.recorder.record("workflow.transition", {"state": session.state.current})

            source, source_ref = session.recorder.call_tool(
                kind="tool.inspect_location",
                tool_name="inspect_location",
                arguments={"id": session.intent.source, "snapshot_id": snapshot.snapshot_id},
                operation=lambda: session.world.inspect_location(
                    session.intent.source, snapshot.snapshot_id
                ),
            )
            destination, destination_ref = session.recorder.call_tool(
                kind="tool.inspect_location",
                tool_name="inspect_location",
                arguments={
                    "id": session.intent.destination,
                    "snapshot_id": snapshot.snapshot_id,
                },
                operation=lambda: session.world.inspect_location(
                    session.intent.destination, snapshot.snapshot_id
                ),
            )
            if not source.exists or not destination.exists:
                session.state.transition(MissionStatus.FAILED_SAFE)
                raise MissionServiceError("source or destination is not a live entity")

            plan, plan_ref = session.recorder.call_tool(
                kind="tool.plan_transport",
                tool_name="plan_transport",
                arguments={"intent": session.intent, "snapshot_id": snapshot.snapshot_id},
                operation=lambda: DeterministicPlanner().plan(
                    intent=session.intent, snapshot=snapshot
                ),
            )
            session.plan = plan
            session.state.transition(MissionStatus.PLANNED)
            session.recorder.record("workflow.transition", {"state": session.state.current})

            proposal_result, _ = session.recorder.call_tool(
                kind="tool.propose_transport",
                tool_name="propose_transport",
                arguments={
                    "intent": session.intent,
                    "snapshot_id": snapshot.snapshot_id,
                    "route_version": plan.route_version,
                    "evidence_refs": [snapshot_ref, source_ref, destination_ref, plan_ref],
                },
                operation=lambda: session.provider.propose_transport(
                    intent=session.intent,
                    snapshot=snapshot,
                    plan=plan,
                    evidence_refs=[snapshot_ref, source_ref, destination_ref, plan_ref],
                ),
            )
            proposal, call = proposal_result
            session.proposal = proposal
            session.recorder.record("llm.proposal", call)
            session.recorder.record("proposal.created", proposal)
            session.state.transition(MissionStatus.PROPOSED)
            session.recorder.record("workflow.transition", {"state": session.state.current})

            proof = SafetyEngine().verify(
                intent=session.intent,
                plan=plan,
                snapshot=snapshot,
                proposal=proposal,
            )
            session.proof = proof
            session.recorder.record("safety.proof", proof)
            if not proof.passed:
                session.state.transition(MissionStatus.REJECTED)
                raise MissionServiceError("deterministic safety proof rejected the proposal")
            session.state.transition(MissionStatus.VERIFIED)
            session.recorder.record("workflow.transition", {"state": session.state.current})
            self._proposal_index[proposal.proposal_id] = session.session_id
            return self._finish_operation(session, name="prepare", idempotency_key=idempotency_key)

    def approve(
        self,
        proposal_id: str,
        *,
        actor: str,
        actor_role: str,
        idempotency_key: str,
        expected_version: int,
    ) -> MissionSession:
        with self._lock:
            session = self._by_proposal(proposal_id)
            self._require_role(actor_role, {"approver", "admin"})
            operation = self._begin_operation(
                session,
                name="approve",
                idempotency_key=idempotency_key,
                expected_version=expected_version,
                payload={"proposal_id": proposal_id, "actor": actor, "role": actor_role},
            )
            if operation is not None:
                return operation
            if session.state.current != MissionStatus.VERIFIED or session.proposal is None:
                raise MissionServiceError("only a VERIFIED proposal can be approved")
            approval, _ = session.recorder.call_tool(
                kind="tool.approve_transport",
                tool_name="approve_transport",
                arguments={"proposal_id": proposal_id, "actor": actor, "role": actor_role},
                operation=lambda: ApprovalToken.issue(
                    proposal_hash=session.proposal.proposal_hash,
                    goal_hash=session.intent.goal_hash,
                    actor=actor,
                    actor_role=actor_role,
                ),
            )
            if not approval.valid_for(session.proposal):
                raise MissionServiceError("approval integrity check failed")
            session.approval = approval
            session.recorder.record("approval.granted", approval)
            session.state.transition(MissionStatus.APPROVED)
            session.recorder.record("workflow.transition", {"state": session.state.current})

            if session.plan is None:
                raise MissionServiceError("approved session has no deterministic route")
            session.mission = Mission(
                mission_id=f"M-{uuid.uuid4().hex[:10].upper()}",
                proposal_id=session.proposal.proposal_id,
                proposal_hash=session.proposal.proposal_hash,
                goal_hash=session.intent.goal_hash,
                pallet_id=session.intent.pallet_id,
                source=session.intent.source,
                destination=session.intent.destination,
                selected_agv=session.plan.selected_agv,
                route=session.plan.nodes,
                route_version=session.plan.route_version,
                map_version=session.plan.map_version,
                snapshot_id=session.proposal.snapshot_id,
                proof_hash=session.proof.proof_hash if session.proof else "",
                status=MissionStatus.APPROVED,
                idempotency_key=f"dispatch:{session.proposal.proposal_hash}",
            )
            self._mission_index[session.mission.mission_id] = session.session_id
            return self._finish_operation(session, name="approve", idempotency_key=idempotency_key)

    def reject(
        self,
        proposal_id: str,
        *,
        actor: str,
        actor_role: str,
        reason: str,
        idempotency_key: str,
        expected_version: int,
    ) -> MissionSession:
        with self._lock:
            session = self._by_proposal(proposal_id)
            self._require_role(actor_role, {"approver", "admin"})
            operation = self._begin_operation(
                session,
                name="reject",
                idempotency_key=idempotency_key,
                expected_version=expected_version,
                payload={
                    "proposal_id": proposal_id,
                    "actor": actor,
                    "role": actor_role,
                    "reason": reason,
                },
            )
            if operation is not None:
                return operation
            if session.state.current != MissionStatus.VERIFIED:
                raise MissionServiceError("only a VERIFIED proposal can be rejected")
            session.rejection_reason = reason
            session.recorder.record(
                "approval.rejected",
                {"proposal_id": proposal_id, "actor": actor, "role": actor_role, "reason": reason},
            )
            session.recorder.record(
                "tool.reject_transport",
                {
                    "tool": "reject_transport",
                    "arguments": {
                        "proposal_id": proposal_id,
                        "actor": actor,
                        "role": actor_role,
                        "reason": reason,
                    },
                    "arguments_hash": canonical_hash(
                        {
                            "proposal_id": proposal_id,
                            "actor": actor,
                            "role": actor_role,
                            "reason": reason,
                        }
                    ),
                    "result": {"state": "REJECTED"},
                    "result_hash": canonical_hash({"state": "REJECTED"}),
                    "latency_ms": 0.0,
                    "error": None,
                },
            )
            session.state.transition(MissionStatus.REJECTED)
            session.recorder.record("workflow.transition", {"state": session.state.current})
            return self._finish_operation(session, name="reject", idempotency_key=idempotency_key)

    def start(
        self,
        mission_id: str,
        *,
        actor: str,
        actor_role: str,
        idempotency_key: str,
        expected_version: int,
    ) -> MissionSession:
        with self._lock:
            session = self._by_mission(mission_id)
            self._require_role(actor_role, {"executor", "admin"})
            operation = self._begin_operation(
                session,
                name="start",
                idempotency_key=idempotency_key,
                expected_version=expected_version,
                payload={"mission_id": mission_id, "actor": actor, "role": actor_role},
            )
            if operation is not None:
                return operation
            if session.mission is None or session.approval is None or session.proposal is None:
                raise MissionServiceError("mission has no valid approval context")
            if session.state.current != MissionStatus.APPROVED:
                raise MissionServiceError("mission start requires APPROVED state")
            if not session.approval.valid_for(session.proposal):
                session.state.transition(MissionStatus.FAILED_SAFE)
                raise MissionServiceError(
                    "approval is stale, expired, or bound to another proposal"
                )
            session.mission, _ = session.recorder.call_tool(
                kind="tool.start_mission",
                tool_name="start_mission",
                arguments={
                    "mission_id": mission_id,
                    "actor": actor,
                    "role": actor_role,
                    "idempotency_key": session.mission.idempotency_key,
                },
                operation=lambda: session.adapter.start(session.mission),
            )
            session.state.transition(MissionStatus.EXECUTING)
            session.recorder.record("execution.started", session.mission)
            session.recorder.record("workflow.transition", {"state": session.state.current})
            session.mission = session.adapter.advance(mission_id)
            session.recorder.record("execution.telemetry", session.mission)
            return self._finish_operation(session, name="start", idempotency_key=idempotency_key)

    def stop(
        self,
        mission_id: str,
        *,
        actor: str,
        actor_role: str,
        trigger_source: str,
        idempotency_key: str,
        expected_version: int,
    ) -> MissionSession:
        with self._lock:
            session = self._by_mission(mission_id)
            self._require_role(actor_role, {"safety", "executor", "admin"})
            operation = self._begin_operation(
                session,
                name="stop",
                idempotency_key=idempotency_key,
                expected_version=expected_version,
                payload={
                    "mission_id": mission_id,
                    "actor": actor,
                    "role": actor_role,
                    "trigger_source": trigger_source,
                },
            )
            if operation is not None:
                return operation
            if session.state.current != MissionStatus.EXECUTING:
                raise MissionServiceError("stop requires EXECUTING state")
            obstacle = session.world.add_hero_blockage()
            session.recorder.record(
                "sensor.aisle_blocked",
                {
                    "obstacle": obstacle,
                    "stop_actor": actor,
                    "trigger_source": trigger_source,
                },
            )
            session.state.transition(MissionStatus.BLOCKED)
            session.recorder.record("workflow.transition", {"state": session.state.current})
            session.stop_latency_ms, _ = session.recorder.call_tool(
                kind="tool.stop_mission",
                tool_name="stop_mission",
                arguments={"mission_id": mission_id, "trigger_source": trigger_source},
                operation=lambda: session.adapter.local_stop(
                    mission_id, source=trigger_source
                ),
            )
            if session.mission is not None:
                session.mission = session.adapter.get(session.mission.mission_id)
            session.recorder.record(
                "execution.local_stop",
                {
                    "mission_id": mission_id,
                    "trigger_source": obstacle.id,
                    "latency_ms": session.stop_latency_ms,
                    "measurement_kind": "simulated_process",
                },
            )
            session.state.transition(MissionStatus.SAFE_STOP)
            session.recorder.record("workflow.transition", {"state": session.state.current})
            return self._finish_operation(session, name="stop", idempotency_key=idempotency_key)

    def replan(
        self,
        mission_id: str,
        *,
        actor: str,
        actor_role: str,
        blocked_node_id: str | None,
        idempotency_key: str,
        expected_version: int,
    ) -> MissionSession:
        with self._lock:
            session = self._by_mission(mission_id)
            self._require_role(actor_role, {"operator", "executor", "admin"})
            operation = self._begin_operation(
                session,
                name="replan",
                idempotency_key=idempotency_key,
                expected_version=expected_version,
                payload={
                    "mission_id": mission_id,
                    "actor": actor,
                    "role": actor_role,
                    "blocked_node_id": blocked_node_id,
                },
            )
            if operation is not None:
                return operation
            if (
                session.state.current != MissionStatus.SAFE_STOP
                or session.mission is None
                or session.proposal is None
                or session.approval is None
            ):
                raise MissionServiceError("replan requires SAFE_STOP and approval context")
            snapshot, _ = session.recorder.call_tool(
                kind="tool.get_operational_snapshot",
                tool_name="get_operational_snapshot",
                arguments={"reason": "blockage_recovery"},
                operation=session.world.snapshot,
            )
            effective_blocked_node = blocked_node_id or self.scenario.blockage.node_id
            recovery_result, _ = session.recorder.call_tool(
                kind="tool.propose_recovery",
                tool_name="propose_recovery",
                arguments={
                    "mission_id": mission_id,
                    "goal_hash": session.intent.goal_hash,
                    "blocked_node_id": effective_blocked_node,
                    "snapshot_id": snapshot.snapshot_id,
                },
                operation=lambda: session.provider.recover_from_blockage(
                    mission_id=mission_id,
                    goal_hash=session.intent.goal_hash,
                    blocked_node_id=effective_blocked_node,
                    snapshot=snapshot,
                ),
            )
            recovery, recovery_call = recovery_result
            session.recovery = recovery
            session.recorder.record("llm.recovery", recovery_call)
            session.recorder.record("recovery.intent", recovery)
            if (
                recovery.action != "REPLAN"
                or recovery.preserve_goal_hash != session.intent.goal_hash
            ):
                session.state.transition(MissionStatus.FAILED_SAFE)
                raise MissionServiceError("recovery intent did not preserve the approved goal")
            session.state.transition(MissionStatus.REPLANNING)
            session.recorder.record("workflow.transition", {"state": session.state.current})
            plan, _ = session.recorder.call_tool(
                kind="tool.replan_mission",
                tool_name="replan_mission",
                arguments={
                    "mission_id": mission_id,
                    "snapshot_id": snapshot.snapshot_id,
                    "start_node": session.world.agvs[session.mission.selected_agv].node_id,
                    "force_agv": session.mission.selected_agv,
                },
                operation=lambda: DeterministicPlanner().plan(
                    intent=session.intent,
                    snapshot=snapshot,
                    start_node=session.world.agvs[session.mission.selected_agv].node_id,
                    force_agv=session.mission.selected_agv,
                ),
            )
            session.replan = plan
            proof = SafetyEngine().verify_replan(
                intent=session.intent,
                plan=plan,
                snapshot=snapshot,
                original_proposal=session.proposal,
            )
            session.replan_proof = proof
            session.recorder.record("safety.replan_proof", proof)
            if not proof.passed or not (
                session.approval.goal_hash == session.intent.goal_hash
                and session.approval.issued_at <= utc_now() < session.approval.expires_at
            ):
                session.state.transition(MissionStatus.FAILED_SAFE)
                raise MissionServiceError("equivalent-route replan proof or approval scope failed")
            session.state.transition(MissionStatus.VERIFIED)
            session.recorder.record(
                "workflow.transition",
                {"state": session.state.current, "authorization": "equivalent-route-policy"},
            )
            return self._finish_operation(session, name="replan", idempotency_key=idempotency_key)

    def resume_and_complete(
        self,
        mission_id: str,
        *,
        actor: str,
        actor_role: str,
        idempotency_key: str,
        expected_version: int,
    ) -> MissionSession:
        with self._lock:
            session = self._by_mission(mission_id)
            self._require_role(actor_role, {"executor", "admin"})
            operation = self._begin_operation(
                session,
                name="resume",
                idempotency_key=idempotency_key,
                expected_version=expected_version,
                payload={"mission_id": mission_id, "actor": actor, "role": actor_role},
            )
            if operation is not None:
                return operation
            if (
                session.state.current != MissionStatus.VERIFIED
                or session.mission is None
                or session.replan is None
                or session.replan_proof is None
                or not session.replan_proof.passed
                or session.approval is None
                or session.proposal is None
                or not session.approval.valid_for(session.proposal)
            ):
                raise MissionServiceError(
                    "resume requires a valid equivalent-route proof and approval"
                )
            session.mission, _ = session.recorder.call_tool(
                kind="tool.resume_mission",
                tool_name="resume_mission",
                arguments={
                    "mission_id": mission_id,
                    "route_version": session.replan.route_version,
                    "actor": actor,
                },
                operation=lambda: session.adapter.replace_route(mission_id, session.replan),
            )
            session.state.transition(MissionStatus.EXECUTING)
            session.recorder.record(
                "execution.resumed",
                {"mission": session.mission, "actor": actor, "role": actor_role},
            )
            session.recorder.record("workflow.transition", {"state": session.state.current})
            while session.mission.status == MissionStatus.EXECUTING:
                session.mission = session.adapter.advance(mission_id)
                session.recorder.record("execution.telemetry", session.mission)
            session.state.transition(MissionStatus.COMPLETED)
            session.recorder.record("workflow.transition", {"state": session.state.current})
            session.recorder.record(
                "outcome.completed",
                {
                    "mission_id": mission_id,
                    "final_node": session.world.agvs[session.mission.selected_agv].node_id,
                    "destination_occupancy": session.world.locations[
                        session.intent.destination
                    ].occupancy,
                    "total_duration_ms": round(
                        (utc_now() - session.created_at).total_seconds() * 1000, 6
                    ),
                    "human_interventions": 2,
                    "estimated_model_cost_usd": 0.0,
                    "measurement_scope": "current_process_reference_simulator",
                },
            )
            session.recorder.export_json()
            return self._finish_operation(session, name="resume", idempotency_key=idempotency_key)

    def override_to_failed_safe(
        self,
        mission_id: str,
        *,
        actor: str,
        actor_role: str,
        reason: str,
        idempotency_key: str,
        expected_version: int,
    ) -> MissionSession:
        with self._lock:
            session = self._by_mission(mission_id)
            self._require_role(actor_role, {"safety", "admin"})
            operation = self._begin_operation(
                session,
                name="override",
                idempotency_key=idempotency_key,
                expected_version=expected_version,
                payload={
                    "mission_id": mission_id,
                    "actor": actor,
                    "role": actor_role,
                    "reason": reason,
                },
            )
            if operation is not None:
                return operation
            if session.state.current not in {MissionStatus.SAFE_STOP, MissionStatus.VERIFIED}:
                raise MissionServiceError("override is allowed only while safely stopped")
            session.recorder.record(
                "safety.override",
                {
                    "mission_id": mission_id,
                    "actor": actor,
                    "role": actor_role,
                    "reason": reason,
                    "effect": "FAILED_SAFE; no motion authorized",
                },
            )
            session.recorder.record(
                "tool.override_mission",
                {
                    "tool": "override_mission",
                    "arguments": {
                        "mission_id": mission_id,
                        "actor": actor,
                        "role": actor_role,
                        "reason": reason,
                    },
                    "arguments_hash": canonical_hash(
                        {
                            "mission_id": mission_id,
                            "actor": actor,
                            "role": actor_role,
                            "reason": reason,
                        }
                    ),
                    "result": {"state": "FAILED_SAFE", "motion_authorized": False},
                    "result_hash": canonical_hash(
                        {"state": "FAILED_SAFE", "motion_authorized": False}
                    ),
                    "latency_ms": 0.0,
                    "error": None,
                },
            )
            session.approval = None
            session.state.transition(MissionStatus.FAILED_SAFE)
            session.recorder.record("workflow.transition", {"state": session.state.current})
            session.recorder.export_json()
            return self._finish_operation(
                session, name="override", idempotency_key=idempotency_key
            )

    def proof(self, proposal_id: str) -> SafetyProof:
        session = self._by_proposal(proposal_id)
        if session.proof is None:
            raise MissionServiceError("proposal has no proof")
        return session.proof

    def status(self, mission_id: str) -> dict[str, Any]:
        session = self._by_mission(mission_id)
        result, _ = session.recorder.call_tool(
            kind="tool.get_mission_status",
            tool_name="get_mission_status",
            arguments={"mission_id": mission_id},
            operation=lambda: self._view(session),
        )
        return result

    def trace(self, trace_id: str) -> list[dict[str, Any]]:
        session_id = self._trace_index.get(trace_id)
        if session_id is None:
            raise MissionServiceError("unknown trace")
        path = self._sessions[session_id].recorder.path
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def metrics(self) -> dict[str, Any]:
        sessions = list(self._sessions.values())
        completed = sum(session.state.current == MissionStatus.COMPLETED for session in sessions)
        return {
            "measurement_scope": "current_process_reference_simulator",
            "sample_size": len(sessions),
            "completed": completed,
            "completion_rate": completed / len(sessions) if sessions else None,
            "stop_latency_ms": [
                session.stop_latency_ms
                for session in sessions
                if session.stop_latency_ms is not None
            ],
        }

    @staticmethod
    def _view(session: MissionSession) -> dict[str, Any]:
        return {
            "intent_id": session.session_id,
            "trace_id": session.recorder.trace_id,
            "state": session.state.current,
            "state_history": session.state.history,
            "intent": session.intent,
            "proposal": session.proposal,
            "proof": session.proof,
            "approval": session.approval,
            "mission": session.mission,
            "replan": session.replan,
            "recovery": session.recovery,
            "replan_proof": session.replan_proof,
            "stop_latency_ms": session.stop_latency_ms,
            "version": session.version,
            "rejection_reason": session.rejection_reason,
            "provider": session.provider.provider_name,
            "model": session.provider.model_name,
        }

    def view(self, session: MissionSession) -> dict[str, Any]:
        return self._view(session)

    def _session(self, session_id: str) -> MissionSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise MissionServiceError("unknown intent session") from exc

    def _by_proposal(self, proposal_id: str) -> MissionSession:
        try:
            return self._session(self._proposal_index[proposal_id])
        except KeyError as exc:
            raise MissionServiceError("unknown proposal") from exc

    def _by_mission(self, mission_id: str) -> MissionSession:
        try:
            return self._session(self._mission_index[mission_id])
        except KeyError as exc:
            raise MissionServiceError("unknown mission") from exc

    def _begin_operation(
        self,
        session: MissionSession,
        *,
        name: str,
        idempotency_key: str,
        expected_version: int,
        payload: dict[str, Any],
    ) -> MissionSession | None:
        operation_key = f"{name}:{idempotency_key}"
        fingerprint = canonical_hash(payload)
        prior = self._operations.get(operation_key)
        if prior is not None:
            prior_fingerprint, prior_session_id = prior
            if prior_fingerprint != fingerprint or prior_session_id != session.session_id:
                raise MissionConflictError("idempotency key was reused with different input")
            return session
        if expected_version != session.version:
            raise MissionConflictError(
                f"stale version: expected {expected_version}, current {session.version}"
            )
        session.recorder.record(
            "api.operation.accepted",
            {
                "operation": name,
                "idempotency_key_hash": canonical_hash(idempotency_key),
                "expected_version": expected_version,
            },
        )
        self._pending_operations[operation_key] = (fingerprint, session.session_id)
        return None

    def _finish_operation(
        self,
        session: MissionSession,
        *,
        name: str,
        idempotency_key: str,
    ) -> MissionSession:
        session.version += 1
        if session.mission is not None:
            session.mission.version = session.version
        operation_key = f"{name}:{idempotency_key}"
        self._operations[operation_key] = self._pending_operations.pop(operation_key)
        session.recorder.record(
            "api.operation.committed",
            {"operation": name, "version": session.version},
        )
        return session

    @staticmethod
    def _require_role(actor_role: str, allowed: set[str]) -> None:
        if actor_role not in allowed:
            raise MissionPermissionError(
                f"role {actor_role!r} is not allowed; expected one of {sorted(allowed)}"
            )
