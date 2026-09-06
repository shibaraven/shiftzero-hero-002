from __future__ import annotations

import json
from datetime import UTC, datetime

from shiftzero.competition_simulation import (
    build_competition_simulation_evidence,
    verify_competition_simulation_evidence,
)
from shiftzero.physical_evidence import validate_physical_evidence


def test_no_hardware_simulation_passes_but_never_becomes_physical(tmp_path) -> None:
    output = tmp_path / "simulation.json"
    report = build_competition_simulation_evidence(
        output_path=output,
        base_time=datetime(2026, 9, 6, tzinfo=UTC),
        sensor_to_stop_ms=150,
    )

    assert verify_competition_simulation_evidence(report)
    assert report["assertions"]["a06_simulation_passed"] is True
    assert report["assertions"]["a07_simulation_passed"] is True
    assert report["eligibility"]["physical_hardware_claimed"] is False

    physical_report = validate_physical_evidence(input_path=output)
    assert physical_report["passed"] is False


def test_simulation_evidence_hash_detects_tampering(tmp_path) -> None:
    output = tmp_path / "simulation.json"
    build_competition_simulation_evidence(
        output_path=output,
        base_time=datetime(2026, 9, 6, tzinfo=UTC),
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    report["outcome"]["final_pose"]["x"] = 999

    assert verify_competition_simulation_evidence(report) is False
