from datetime import timedelta

from shiftzero.agent import FixtureProvider
from shiftzero.domain import ApprovalToken, MissionIntent, utc_now
from shiftzero.simulator import DeterministicPlanner, ReferenceWorld, load_default_scenario


def test_approval_is_bound_to_exact_proposal_hash() -> None:
    world = ReferenceWorld(load_default_scenario())
    snapshot = world.snapshot()
    intent = MissionIntent(pallet_id="P-104", source="INBOUND-01", destination="RACK-A12")
    plan = DeterministicPlanner().plan(intent=intent, snapshot=snapshot)
    proposal, _ = FixtureProvider().propose_transport(
        intent=intent,
        snapshot=snapshot,
        plan=plan,
        evidence_refs=["snapshot:test", "location:test"],
    )
    approval = ApprovalToken.issue(
        proposal_hash=proposal.proposal_hash,
        goal_hash=intent.goal_hash,
        actor="approver",
    )
    changed = proposal.model_copy(update={"proposal_hash": "changed"})
    assert approval.valid_for(proposal)
    assert not approval.valid_for(changed)


def test_expired_approval_is_invalid() -> None:
    world = ReferenceWorld(load_default_scenario())
    snapshot = world.snapshot()
    intent = MissionIntent(pallet_id="P-104", source="INBOUND-01", destination="RACK-A12")
    plan = DeterministicPlanner().plan(intent=intent, snapshot=snapshot)
    proposal, _ = FixtureProvider().propose_transport(
        intent=intent,
        snapshot=snapshot,
        plan=plan,
        evidence_refs=["snapshot:test", "location:test"],
    )
    approval = ApprovalToken.issue(
        proposal_hash=proposal.proposal_hash,
        goal_hash=intent.goal_hash,
        actor="approver",
        lifetime=timedelta(seconds=-1),
    )
    assert not approval.valid_for(proposal, at=utc_now())
