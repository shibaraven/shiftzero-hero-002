from datetime import timedelta

from shiftzero.agent import FixtureProvider
from shiftzero.domain import ApprovalToken, MissionIntent, RouteReservation, TransportProposal
from shiftzero.safety import SafetyEngine
from shiftzero.simulator import DeterministicPlanner, ReferenceWorld, load_default_scenario


def _proposal_setup():
    world = ReferenceWorld(load_default_scenario())
    snapshot = world.snapshot()
    intent = MissionIntent(
        pallet_id="P-104",
        source="INBOUND-01",
        destination="RACK-A12",
    )
    plan = DeterministicPlanner().plan(intent=intent, snapshot=snapshot)
    proposal, _ = FixtureProvider().propose_transport(
        intent=intent,
        snapshot=snapshot,
        plan=plan,
        evidence_refs=["snapshot:test", "location:test"],
    )
    return world, snapshot, intent, plan, proposal


def test_nominal_proposal_passes_all_safety_checks() -> None:
    _, snapshot, intent, plan, proposal = _proposal_setup()
    proof = SafetyEngine().verify(intent=intent, plan=plan, snapshot=snapshot, proposal=proposal)
    assert proof.passed
    assert all(check.passed for check in proof.checks)


def test_execution_proof_seals_approval_integrity() -> None:
    _, snapshot, intent, plan, proposal = _proposal_setup()
    engine = SafetyEngine()
    route_proof = engine.verify(
        intent=intent, plan=plan, snapshot=snapshot, proposal=proposal
    )
    approval = ApprovalToken.issue(
        proposal_hash=proposal.proposal_hash,
        goal_hash=intent.goal_hash,
        actor="safety-test",
    )
    proof = engine.bind_approval_integrity(
        proof=route_proof,
        proposal=proposal,
        approval=approval,
    )
    check = next(check for check in proof.checks if check.name == "approval_integrity")
    assert proof.passed
    assert check.passed
    assert "actor=safety-test" in check.detail


def test_execution_proof_rejects_tampered_approval() -> None:
    _, snapshot, intent, plan, proposal = _proposal_setup()
    engine = SafetyEngine()
    route_proof = engine.verify(
        intent=intent, plan=plan, snapshot=snapshot, proposal=proposal
    )
    approval = ApprovalToken.issue(
        proposal_hash=proposal.proposal_hash,
        goal_hash=intent.goal_hash,
        actor="safety-test",
    ).model_copy(update={"actor": "tampered-actor"})
    proof = engine.bind_approval_integrity(
        proof=route_proof,
        proposal=proposal,
        approval=approval,
    )
    check = next(check for check in proof.checks if check.name == "approval_integrity")
    assert not proof.passed
    assert not check.passed


def test_schema_valid_wrong_entity_is_rejected() -> None:
    _, snapshot, intent, plan, proposal = _proposal_setup()
    invalid_intent = intent.model_copy(update={"pallet_id": "P-999"})
    proof = SafetyEngine().verify(
        intent=invalid_intent,
        plan=plan,
        snapshot=snapshot,
        proposal=proposal,
    )
    assert not proof.passed
    assert not next(check for check in proof.checks if check.name == "entity_validity").passed


def test_stale_snapshot_is_rejected() -> None:
    world, _, intent, plan, proposal = _proposal_setup()
    newer_snapshot = world.snapshot()
    proof = SafetyEngine().verify(
        intent=intent,
        plan=plan,
        snapshot=newer_snapshot,
        proposal=proposal,
    )
    assert not proof.passed
    assert not next(check for check in proof.checks if check.name == "map_consistency").passed


def test_blockage_forces_alternate_route() -> None:
    world, _, intent, original_plan, _ = _proposal_setup()
    assert "N09" in original_plan.nodes
    world.add_hero_blockage()
    snapshot = world.snapshot()
    replan = DeterministicPlanner().plan(
        intent=intent,
        snapshot=snapshot,
        start_node="N04",
        force_agv="AGV-03",
    )
    assert "N09" not in replan.nodes
    assert replan.nodes == ["N04", "N05", "N10", "N12"]


def test_temporal_reservation_collision_is_rejected() -> None:
    _, snapshot, intent, plan, _ = _proposal_setup()
    reservation = RouteReservation(
        reservation_group=plan.reservation_groups[0],
        held_by="AGV-99",
        starts_at=snapshot.captured_at,
        ends_at=snapshot.captured_at + timedelta(seconds=10),
    )
    snapshot = snapshot.model_copy(update={"route_reservations": [reservation]})
    proposal = TransportProposal.issue(
        proposal_id="TP-TEMPORAL",
        intent=intent,
        plan=plan,
        snapshot_id=snapshot.snapshot_id,
        evidence_refs=["snapshot:test", "plan:test"],
    )
    proof = SafetyEngine().verify(
        intent=intent, plan=plan, snapshot=snapshot, proposal=proposal
    )
    assert not next(check for check in proof.checks if check.name == "collision").passed


def test_circular_wait_is_rejected_as_deadlock() -> None:
    _, snapshot, intent, plan, _ = _proposal_setup()
    snapshot = snapshot.model_copy(
        update={"wait_for": {plan.selected_agv: "AGV-07", "AGV-07": plan.selected_agv}}
    )
    proposal = TransportProposal.issue(
        proposal_id="TP-DEADLOCK",
        intent=intent,
        plan=plan,
        snapshot_id=snapshot.snapshot_id,
        evidence_refs=["snapshot:test", "plan:test"],
    )
    proof = SafetyEngine().verify(
        intent=intent, plan=plan, snapshot=snapshot, proposal=proposal
    )
    assert not next(check for check in proof.checks if check.name == "deadlock").passed


def test_single_medium_confidence_observation_is_not_persistent_collision() -> None:
    world, _, intent, plan, _ = _proposal_setup()
    obstacle = world.add_hero_blockage()
    obstacle.confidence = 0.6
    obstacle.observation_count = 1
    snapshot = world.snapshot()
    proposal = TransportProposal.issue(
        proposal_id="TP-FILTERED-OBSERVATION",
        intent=intent,
        plan=plan,
        snapshot_id=snapshot.snapshot_id,
        evidence_refs=["snapshot:test", "plan:test"],
    )
    proof = SafetyEngine().verify(
        intent=intent, plan=plan, snapshot=snapshot, proposal=proposal
    )
    assert next(check for check in proof.checks if check.name == "collision").passed
