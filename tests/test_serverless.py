from __future__ import annotations

import json
from pathlib import Path

from shiftzero.serverless import build_serverless_readiness

ROOT = Path(__file__).resolve().parents[1]


def test_serverless_readiness_separates_artifact_from_cloud(tmp_path: Path) -> None:
    smoke = tmp_path / "serverless-smoke"
    smoke.mkdir()
    (smoke / "metrics.json").write_text(
        json.dumps(
            {"sample_size": 100, "validated_count": 100, "safety_violation_count": 0}
        ),
        encoding="utf-8",
    )
    (smoke / "run-manifest.json").write_text("{}", encoding="utf-8")
    (smoke / "scenario-results.jsonl").write_text("{}\n", encoding="utf-8")
    report = build_serverless_readiness(
        root=ROOT,
        output_path=tmp_path / "readiness.json",
        smoke_output=smoke,
    )
    assert report["artifact_ready"] is True
    assert report["local_artifact"]["smoke_test_passed"] is True
    assert report["cloud_deployed"] is False
    assert report["blockers"]
