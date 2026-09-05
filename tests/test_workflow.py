import json
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
    assert Path(result.evidence_path).with_suffix(".json").is_file()
    assert len(result.model_calls) == 3
    assert result.model_calls[-1].tool_name == "propose_recovery"
    events = [
        json.loads(line)
        for line in Path(result.evidence_path).read_text(encoding="utf-8").splitlines()
    ]
    required = {
        "tool",
        "arguments",
        "arguments_hash",
        "result",
        "result_hash",
        "latency_ms",
        "error",
    }
    assert all(
        required <= set(event["payload"])
        for event in events
        if event["kind"].startswith("tool.")
    )
    outcome = next(event["payload"] for event in events if event["kind"] == "outcome.completed")
    assert outcome["total_duration_ms"] > 0
    assert outcome["human_interventions"] == 1
    assert "estimated_model_cost_usd" in outcome
    assert outcome["final_node"] == "N12"
    assert outcome["final_pose"] == {
        "node_id": "N12",
        "x": 6.0,
        "y": 0.0,
        "heading_deg": 315.0,
    }
    assert outcome["destination_occupancy"] == "P-104"


def test_fixture_is_never_labeled_as_nebius(tmp_path: Path) -> None:
    result = WorkflowController(
        scenario=load_default_scenario(),
        provider=FixtureProvider(),
        evidence_root=tmp_path,
    ).run_hero()
    assert result.provider == "fixture"
    assert "not-a-model" in result.model
    assert all(call.provider == "fixture" for call in result.model_calls)
