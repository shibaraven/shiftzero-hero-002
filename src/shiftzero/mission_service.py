from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
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
    RoutePlan,
    SafetyProof,
    TransportProposal,
    utc_now,
)
from shiftzero.evidence import EvidenceRecorder
from shiftzero.safety import SafetyEngine
from shiftzero.simulator import DeterministicPlanner, HeroScenario, ReferenceWorld
from shiftzero.state_machine import WorkflowState


class MissionServiceError(RuntimeError):
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


class MissionService:
    def __init__(self, *, scenario: HeroScenario, evidence_root: Path) -> None:
        self.scenario = scenario
        self.evidence_root = evidence_root
        self._sessions: dict[str, MissionSession] = {}
        self._proposal_index: dict[str, str] = {}
        self._mission_index: dict[str, str] = {}
        self._trace_index: dict[str, str] = {}
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

    def prepare_proposal(self, session_id: str) -> MissionSession:
        with self._lock:
            session = self._session(session_id)
            if session.state.current != MissionStatus.INTENT:
                raise MissionServiceError("proposal preparation requires INTENT state")
            snapshot = session.world.snapshot()
            session.snapshot = snapshot
            snapshot_ref = session.recorder.record("tool.get_operational_snapshot", snapshot)
            session.state.transition(MissionStatus.OBSERVED)
            session.recorder.record("workflow.transition", {"state": session.state.current})

            source = session.world.inspect_location(session.intent.source, snapshot.snapshot_id)
            destination = session.world.inspect_location(
                session.intent.destination, snapshot.snapshot_id
            )
            source_ref = session.recorder.record("tool.inspect_location", source)
            destination_ref = session.recorder.record("tool.inspect_location", destination)
            if not source.exists or not destination.exists:
                session.state.transition(MissionStatus.FAILED_SAFE)
                raise MissionServiceError("source or destination is not a live entity")

            plan = DeterministicPlanner().plan(intent=session.intent, snapshot=snapshot)
            session.plan = plan
            plan_ref = session.recorder.record("tool.plan_transport", plan)
            session.state.transition(MissionStatus.PLANNED)
            session.recorder.record("workflow.transition", {"state": session.state.current})

            proposal, call = session.provider.propose_transport(
                intent=session.intent,
                snapshot=snapshot,
                plan=plan,
                evidence_refs=[snapshot_ref, source_ref, destination_ref, plan_ref],
            )
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
            return session

    def approve(self, proposal_id: str, *, actor: str) -> MissionSession:
        with self._lock:
            session = self._by_proposal(proposal_id)
            if session.state.current != MissionStatus.VERIFIED or session.proposal is None:
                raise MissionServiceError("only a VERIFIED proposal can be approved")
            approval = ApprovalToken.issue(
                proposal_hash=session.proposal.proposal_hash,
                goal_hash=session.intent.goal_hash,
                actor=actor,
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
                status=MissionStatus.APPROVED,
                idempotency_key=f"dispatch:{session.proposal.proposal_hash}",
            )
            self._mission_index[session.mission.mission_id] = session.session_id
            return session

    def start(self, mission_id: str) -> MissionSession:
        with self._lock:
            session = self._by_mission(mission_id)
            if session.mission is None or session.approval is None or session.proposal is None:
                raise MissionServiceError("mission has no valid approval context")
            if session.state.current != MissionStatus.APPROVED:
                raise MissionServiceError("mission start requires APPROVED state")
            if not session.approval.valid_for(session.proposal):
                session.state.transition(MissionStatus.FAILED_SAFE)
                raise MissionServiceError(
                    "approval is stale, expired, or bound to another proposal"
                )
            session.mission = session.adapter.start(session.mission)
            session.state.transition(MissionStatus.EXECUTING)
            session.recorder.record("execution.started", session.mission)
            session.recorder.record("workflow.transition", {"state": session.state.current})
            session.mission = session.adapter.advance(mission_id)
            session.recorder.record("execution.telemetry", session.mission)
            return session

    def stop(self, mission_id: str, *, actor: str) -> MissionSession:
        with self._lock:
            session = self._by_mission(mission_id)
            if session.state.current != MissionStatus.EXECUTING:
                raise MissionServiceError("stop requires EXECUTING state")
            obstacle = session.world.add_hero_blockage()
            session.recorder.record(
                "sensor.aisle_blocked",
                {"obstacle": obstacle, "stop_actor": actor},
            )
            session.state.transition(MissionStatus.BLOCKED)
            session.recorder.record("workflow.transition", {"state": session.state.current})
            session.stop_latency_ms = session.adapter.local_stop(mission_id, source=obstacle.id)
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
            return session

    def replan_and_complete(self, mission_id: str) -> MissionSession:
        with self._lock:
            session = self._by_mission(mission_id)
            if (
                session.state.current != MissionStatus.SAFE_STOP
                or session.mission is None
                or session.proposal is None
                or session.approval is None
            ):
                raise MissionServiceError("replan requires SAFE_STOP and approval context")
            snapshot = session.world.snapshot()
            session.state.transition(MissionStatus.REPLANNING)
            session.recorder.record("workflow.transition", {"state": session.state.current})
            plan = DeterministicPlanner().plan(
                intent=session.intent,
                snapshot=snapshot,
                start_node=session.world.agvs[session.mission.selected_agv].node_id,
                force_agv=session.mission.selected_agv,
            )
            session.replan = plan
            session.recorder.record("tool.replan_mission", plan)
            proof = SafetyEngine().verify_replan(
                intent=session.intent,
                plan=plan,
                snapshot=snapshot,
                original_proposal=session.proposal,
            )
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
            session.mission = session.adapter.replace_route(mission_id, plan)
            session.state.transition(MissionStatus.EXECUTING)
            session.recorder.record("execution.resumed", session.mission)
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
                },
            )
            return session

    def proof(self, proposal_id: str) -> SafetyProof:
        session = self._by_proposal(proposal_id)
        if session.proof is None:
            raise MissionServiceError("proposal has no proof")
        return session.proof

    def status(self, mission_id: str) -> dict[str, Any]:
        session = self._by_mission(mission_id)
        return self._view(session)

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
            "stop_latency_ms": session.stop_latency_ms,
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
