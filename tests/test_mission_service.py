from pathlib import Path

from shiftzero.agent import FixtureProvider
from shiftzero.domain import MissionStatus
from shiftzero.mission_service import MissionService
from shiftzero.simulator import load_default_scenario


def _safely_stopped_service(tmp_path: Path) -> tuple[MissionService, str, int]:
    service = MissionService(scenario=load_default_scenario(), evidence_root=tmp_path)
    session = service.create_intent(
        operator_text="Move P-104 from INBOUND-01 to RACK-A12",
        operator_id="operator",
        provider=FixtureProvider(),
    )
    session = service.prepare_proposal(
        session.session_id, idempotency_key="prepare-service", expected_version=1
    )
    session = service.approve(
        session.proposal.proposal_id,
        actor="approver",
        actor_role="approver",
        idempotency_key="approve-service",
        expected_version=2,
    )
    mission_id = session.mission.mission_id
    session = service.start(
        mission_id,
        actor="executor",
        actor_role="executor",
        idempotency_key="start-service",
        expected_version=3,
    )
    session = service.stop(
        mission_id,
        actor="safety",
        actor_role="safety",
        trigger_source="safety-sensor",
        idempotency_key="stop-service",
        expected_version=4,
    )
    assert session.state.current == MissionStatus.SAFE_STOP
    return service, mission_id, session.version


def test_override_never_resumes_motion_and_invalidates_approval(tmp_path: Path) -> None:
    service, mission_id, version = _safely_stopped_service(tmp_path)
    session = service.override_to_failed_safe(
        mission_id,
        actor="safety-owner",
        actor_role="safety",
        reason="site owner terminated recovery",
        idempotency_key="override-service",
        expected_version=version,
    )
    assert session.state.current == MissionStatus.FAILED_SAFE
    assert session.approval is None
    assert session.mission.status == MissionStatus.SAFE_STOP
    kinds = [event["kind"] for event in service.trace(session.recorder.trace_id)]
    assert "safety.override" in kinds
    assert "tool.override_mission" in kinds
