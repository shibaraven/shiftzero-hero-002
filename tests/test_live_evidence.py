from __future__ import annotations

from pathlib import Path

from shiftzero.domain import canonical_hash
from shiftzero.live_evidence import build_live_evidence_summary

ROOT = Path(__file__).resolve().parents[1]


def test_live_summary_is_hash_bound_and_complete(tmp_path: Path) -> None:
    report = build_live_evidence_summary(
        root=ROOT,
        output_path=tmp_path / "live-runtime-summary.json",
    )
    report_without_hash = dict(report)
    report_hash = report_without_hash.pop("report_hash")
    assert report_hash == canonical_hash(report_without_hash)
    assert report["compatibility"]["official_gate_passed"] is True
    assert report["compatibility"]["live_run_count"] == 120
    assert report["compatibility"]["model_call_count"] == 360
    assert report["compatibility"]["unique_request_id_count"] == 360
    assert report["compatibility"]["all_trace_chains_valid"] is True
    assert report["measurements"]["replan_mission"]["sample_size"] == 120
    assert report["measurements"]["replan_mission"]["successful_result_count"] == 120
    assert report["measurements"]["cost_kpi"]["total_gate_estimated_usd"] > 0
    assert len(report["representative_live_trace"]["model_calls"]) == 3
