import json
from pathlib import Path

from shiftzero.evaluation import evaluate_scenarios
from shiftzero.simulator import load_default_scenario


def test_100_scenario_matrix_has_zero_safety_violations(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    report = evaluate_scenarios(
        scenario=load_default_scenario(),
        manifest_path=root / "scenarios" / "evaluation_manifest.json",
        output_dir=tmp_path,
    )
    assert report.metrics.sample_size == 100
    assert report.metrics.validated_outcome_rate >= 0.95
    assert report.metrics.safety_violation_count == 0
    assert report.metrics.unsafe_plan_rejection_recall == 1.0
    rows = (tmp_path / "scenario-results.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 100
    assert {json.loads(row)["group_id"] for row in rows} == {
        "S01",
        "S02",
        "S03",
        "S04",
        "S05",
        "S06",
    }
