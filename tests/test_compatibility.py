from pathlib import Path

from shiftzero.agent import FixtureProvider
from shiftzero.compatibility import run_compatibility_gate
from shiftzero.simulator import load_default_scenario


def test_fixture_preflight_can_pass_thresholds_but_never_official_gate(tmp_path: Path) -> None:
    report = run_compatibility_gate(
        scenario=load_default_scenario(),
        provider=FixtureProvider(),
        evidence_root=tmp_path / "runs",
        report_path=tmp_path / "report.json",
        repetitions=4,
    )
    assert report["all_thresholds_passed"]
    assert not report["official_gate_passed"]
    assert not report["real_provider"]
    assert report["fault_controls"]["stale_snapshot_blocked"]
    assert report["fault_controls"]["duplicate_dispatch_idempotent"]
