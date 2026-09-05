from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

from shiftzero.agent import FixtureProvider
from shiftzero.domain import MissionStatus, canonical_hash
from shiftzero.evaluation import _git_commit, _source_tree_hash
from shiftzero.evidence import EvidenceRecorder
from shiftzero.simulator import HeroScenario
from shiftzero.workflow import WorkflowController

EXPECTED_HERO_STATES = [
    MissionStatus.INTENT,
    MissionStatus.OBSERVED,
    MissionStatus.PLANNED,
    MissionStatus.PROPOSED,
    MissionStatus.VERIFIED,
    MissionStatus.APPROVED,
    MissionStatus.EXECUTING,
    MissionStatus.BLOCKED,
    MissionStatus.SAFE_STOP,
    MissionStatus.REPLANNING,
    MissionStatus.VERIFIED,
    MissionStatus.EXECUTING,
    MissionStatus.COMPLETED,
]


def run_hero_reliability(
    *, scenario: HeroScenario, output_dir: Path, runs: int = 20
) -> dict[str, Any]:
    if runs < 1:
        raise ValueError("runs must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    consecutive = 0
    max_consecutive = 0
    for index in range(1, runs + 1):
        started = time.perf_counter_ns()
        result = WorkflowController(
            scenario=scenario.model_copy(deep=True),
            provider=FixtureProvider(),
            evidence_root=output_dir / "runs",
        ).run_hero(approval_actor=f"reliability-run-{index:03d}")
        wall_latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        trace_path = Path(result.evidence_path)
        trace_valid = EvidenceRecorder.verify(trace_path)
        state_path_valid = result.state_history == EXPECTED_HERO_STATES
        passed = (
            result.final_status == MissionStatus.COMPLETED
            and trace_valid
            and state_path_valid
            and result.initial_route_version != result.replan_route_version
        )
        consecutive = consecutive + 1 if passed else 0
        max_consecutive = max(max_consecutive, consecutive)
        records.append(
            {
                "run": index,
                "passed": passed,
                "trace_id": result.trace_id,
                "trace_path": str(trace_path.resolve()),
                "trace_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest(),
                "trace_chain_valid": trace_valid,
                "state_path_valid": state_path_valid,
                "final_status": result.final_status,
                "initial_route_version": result.initial_route_version,
                "replan_route_version": result.replan_route_version,
                "stop_latency_ms": result.stop_latency_ms,
                "stop_latency_kind": result.stop_latency_kind,
                "wall_latency_ms": round(wall_latency_ms, 6),
            }
        )

    stop_latencies = [record["stop_latency_ms"] for record in records]
    wall_latencies = [record["wall_latency_ms"] for record in records]
    passed_count = sum(record["passed"] for record in records)
    root = Path(__file__).resolve().parents[2]
    body: dict[str, Any] = {
        "report_version": "hero-reliability-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "measurement_scope": "reference_simulator_fixture_provider",
        "claims_boundary": (
            "Process timings are local simulator measurements, not physical sensor-to-stop latency."
        ),
        "git_commit": _git_commit(root),
        "source_tree_hash": _source_tree_hash(root),
        "sample_size": runs,
        "passed_count": passed_count,
        "success_rate": passed_count / runs,
        "max_consecutive_passes": max_consecutive,
        "acceptance_criteria": {
            "minimum_consecutive_passes": 20,
            "all_trace_chains_valid": True,
            "all_state_paths_valid": True,
            "all_route_versions_changed_after_blockage": True,
        },
        "acceptance_passed": runs >= 20 and max_consecutive >= 20,
        "stop_latency_ms": _distribution(stop_latencies),
        "wall_latency_ms": _distribution(wall_latencies),
        "runs": records,
    }
    body["report_hash"] = canonical_hash(body)
    report_path = output_dir / "report.json"
    report_path.write_text(
        json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return body


def _distribution(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * 0.95)))
    return {
        "min": round(ordered[0], 6),
        "median": round(median(ordered), 6),
        "p95": round(ordered[p95_index], 6),
        "max": round(ordered[-1], 6),
    }
