from pathlib import Path

from shiftzero.baseline import run_fair_baseline
from shiftzero.simulator import load_default_scenario


def test_fair_baseline_has_twenty_matched_samples_per_flow(tmp_path: Path) -> None:
    report = run_fair_baseline(
        scenario=load_default_scenario(),
        output_path=tmp_path / "baseline.json",
        samples_per_flow=20,
    )
    assert report["sample_size_per_flow"] == 20
    assert report["same_conditions"] is True
    assert report["manual_flow"]["failure_count"] == 0
    assert report["agent_flow"]["failure_count"] == 0
    assert "No labor or time savings claim" in report["claims_boundary"]
