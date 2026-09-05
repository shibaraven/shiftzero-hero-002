from pathlib import Path

from shiftzero.reliability import run_hero_reliability
from shiftzero.simulator import load_default_scenario


def test_hero_reliability_requires_and_proves_twenty_consecutive_runs(tmp_path: Path) -> None:
    report = run_hero_reliability(
        scenario=load_default_scenario(), output_dir=tmp_path, runs=20
    )
    assert report["acceptance_passed"] is True
    assert report["passed_count"] == 20
    assert report["max_consecutive_passes"] == 20
    assert all(run["trace_chain_valid"] for run in report["runs"])
    assert all(run["state_path_valid"] for run in report["runs"])
