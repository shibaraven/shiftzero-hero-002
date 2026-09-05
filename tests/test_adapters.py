from shiftzero.adapters import CompatibilityAttestation, RealAgvAdapter, SimulatorAdapter
from shiftzero.domain import Mission, MissionIntent, MissionStatus
from shiftzero.simulator import DeterministicPlanner, ReferenceWorld, load_default_scenario


def _mission() -> tuple[ReferenceWorld, Mission]:
    world = ReferenceWorld(load_default_scenario())
    snapshot = world.snapshot()
    intent = MissionIntent(pallet_id="P-104", source="INBOUND-01", destination="RACK-A12")
    plan = DeterministicPlanner().plan(intent=intent, snapshot=snapshot)
    return world, Mission(
        mission_id="M-TEST",
        proposal_id="TP-TEST",
        proposal_hash="hash",
        goal_hash=intent.goal_hash,
        pallet_id=intent.pallet_id,
        source=intent.source,
        destination=intent.destination,
        selected_agv=plan.selected_agv,
        route=plan.nodes,
        route_version=plan.route_version,
        status=MissionStatus.APPROVED,
        idempotency_key="same-key",
    )


def test_duplicate_dispatch_creates_one_mission() -> None:
    world, mission = _mission()
    adapter = SimulatorAdapter(world)
    first = adapter.start(mission)
    second = adapter.start(mission)
    assert first.mission_id == second.mission_id
    assert adapter.mission_count == 1


def test_real_adapter_is_blocked_before_official_gate() -> None:
    attestation = CompatibilityAttestation(
        provider="fixture",
        model="deterministic-fixture-not-a-model",
        generated_at="2026-09-05T00:00:00Z",
        official_gate_passed=False,
        report_hash="test",
    )
    try:
        RealAgvAdapter(attestation)
    except RuntimeError as exc:
        assert "official gate" in str(exc)
    else:
        raise AssertionError("real adapter opened without official gate")
