from __future__ import annotations

from pathlib import Path

from shiftzero.release_acceptance import build_release_acceptance


def test_checked_in_acceptance_has_only_external_evidence_gates(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]

    report = build_release_acceptance(
        root=root,
        output_path=tmp_path / "release-acceptance.json",
    )

    assert report["passed_count"] == 8
    assert report["total_count"] == 12
    assert report["failed_ids"] == []
    assert report["blocked_external_ids"] == ["A06", "A07", "A11", "A12"]
    assert report["all_acceptance_passed"] is False

    by_id = {item["id"]: item for item in report["items"]}
    assert all(by_id[acceptance_id]["passed"] is True for acceptance_id in ("A01", "A10"))
    assert by_id["A06"]["status"] == "external_evidence_required"
    assert by_id["A11"]["status"] == "external_evidence_required"
