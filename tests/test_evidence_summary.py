import json
import shutil
from pathlib import Path

from shiftzero.agent import FixtureProvider
from shiftzero.evidence_summary import build_hero_summary
from shiftzero.simulator import load_default_scenario
from shiftzero.workflow import WorkflowController

ROOT = Path(__file__).resolve().parents[1]


def test_summary_serializes_typed_operation_metrics(tmp_path: Path) -> None:
    output_dir = tmp_path / "evidence" / "hero-reliability"
    result = WorkflowController(
        scenario=load_default_scenario(),
        provider=FixtureProvider(),
        evidence_root=output_dir / "runs",
    ).run_hero()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps({"runs": [{"trace_path": result.evidence_path}]}), encoding="utf-8"
    )
    (tmp_path / "schemas").mkdir()
    shutil.copy(ROOT / "schemas" / "safety-policy.json", tmp_path / "schemas")
    summary_path = tmp_path / "evidence" / "hero-summary.json"

    summary = build_hero_summary(root=tmp_path, output_path=summary_path)

    assert summary["summary_version"] == "hero-summary-v4"
    assert summary["operation_metrics"]["schema_version"] == "operation-metrics-v1"
    assert summary["operation_metrics"]["completed"] is True
    assert summary["operation_metrics"]["final_pose"]["node_id"] == "N12"
    assert next(
        check for check in summary["safety_checks"] if check["name"] == "approval_integrity"
    )["passed"] is True
    assert json.loads(summary_path.read_text(encoding="utf-8")) == summary
