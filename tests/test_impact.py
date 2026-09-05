from pathlib import Path

import pytest

from shiftzero.impact import run_impact_load_model
from shiftzero.simulator import load_default_scenario


def test_impact_model_covers_declared_load_range_without_physical_claims(
    tmp_path: Path,
) -> None:
    report = run_impact_load_model(
        scenario=load_default_scenario(),
        output_path=tmp_path / "impact.json",
    )

    assert report["measurement_scope"] == (
        "planning_projection_reference_map_not_physical_measurement"
    )
    assert report["official_or_physical_evidence"] is False
    assert report["assumptions_are_not_measurements"] is True
    assert [row["pallets_per_day"] for row in report["loads"]] == [400, 450, 500]
    assert all(row["sample_days"] == 20 for row in report["loads"])
    assert all(row["simulated_missions"] >= 8000 for row in report["loads"])
    assert report["loads"][0]["operator_impact"]["hours_saved_per_day"] < report["loads"][
        -1
    ]["operator_impact"]["hours_saved_per_day"]
    assert (tmp_path / "impact.json").is_file()


def test_impact_model_rejects_undersized_or_out_of_scope_samples(tmp_path: Path) -> None:
    scenario = load_default_scenario()
    with pytest.raises(ValueError, match="at least 20"):
        run_impact_load_model(
            scenario=scenario,
            output_path=tmp_path / "impact.json",
            sample_days=19,
        )
    with pytest.raises(ValueError, match="400-500"):
        run_impact_load_model(
            scenario=scenario,
            output_path=tmp_path / "impact.json",
            daily_loads=(399, 500),
        )
