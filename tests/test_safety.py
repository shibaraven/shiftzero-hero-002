from shiftzero.agent import FixtureProvider
from shiftzero.domain import MissionIntent
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
