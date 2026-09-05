from pathlib import Path

from shiftzero.agent import FixtureProvider
from shiftzero.domain import MissionStatus
from shiftzero.evidence import EvidenceRecorder
from shiftzero.simulator import load_default_scenario
from shiftzero.workflow import WorkflowController


def test_complete_proof_carrying_hero_loop(tmp_path: Path) -> None:
    result = WorkflowController(
        scenario=load_default_scenario(),
        provider=FixtureProvider(),
        evidence_root=tmp_path,
    ).run_hero()

    assert result.provider == "fixture"
    assert result.final_status == MissionStatus.COMPLETED
    assert result.initial_route_version != result.replan_route_version
    assert result.stop_latency_kind == "simulated_process"
    assert result.stop_latency_ms < 200
    assert MissionStatus.BLOCKED in result.state_history
    assert MissionStatus.SAFE_STOP in result.state_history
    assert MissionStatus.REPLANNING in result.state_history
    assert EvidenceRecorder.verify(Path(result.evidence_path))


def test_fixture_is_never_labeled_as_nebius(tmp_path: Path) -> None:
    result = WorkflowController(
        scenario=load_default_scenario(),
        provider=FixtureProvider(),
        evidence_root=tmp_path,
    ).run_hero()
    assert result.provider == "fixture"
    assert "not-a-model" in result.model
    assert all(call.provider == "fixture" for call in result.model_calls)
