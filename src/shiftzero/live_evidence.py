from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

from shiftzero.domain import canonical_hash
from shiftzero.evidence import EvidenceRecorder

MODEL_SPAN_KINDS = frozenset({"llm.intent", "llm.proposal", "llm.recovery"})
MODEL_TOOLS = frozenset(
    {"parse_mission_intent", "propose_transport", "propose_recovery"}
)


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return math.inf
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _matches_commit(root: Path, commit: str, relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "diff", "--quiet", commit, "--", relative_path],
        cwd=root,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def build_live_evidence_summary(
    *,
    root: Path,
    output_path: Path,
    live_gate_path: Path | None = None,
    live_trace_root: Path | None = None,
    pricing_snapshot_path: Path | None = None,
) -> dict[str, Any]:
    """Aggregate receipts and KPIs from the completed live Compatibility Gate.

    The report is derived from existing trace files. It never sends an inference request and
    never reads an API key. Cost is a catalog-list-price calculation, not a billing receipt.
    """
    root = root.resolve()
    live_gate_path = live_gate_path or root / "evidence/compatibility/live-gate.json"
    live_trace_root = live_trace_root or root / "evidence/runs/live-compatibility"
    pricing_snapshot_path = (
        pricing_snapshot_path
        or root / "evidence/compatibility/token-factory-model-catalog.json"
    )

    gate = json.loads(live_gate_path.read_text(encoding="utf-8"))
    pricing = json.loads(pricing_snapshot_path.read_text(encoding="utf-8"))
    trace_paths = sorted(live_trace_root.glob("*/hero-run.jsonl"))
    if not trace_paths:
        raise ValueError("no live trace JSONL files found")
    if len(trace_paths) != gate["metrics"]["completed_runs"]:
        raise ValueError("live trace count does not match Compatibility Gate")
    if not all(EvidenceRecorder.verify(path) for path in trace_paths):
        raise ValueError("one or more live trace hash chains are invalid")

    events_by_trace = {path: _load_events(path) for path in trace_paths}
    model_events = [
        event
        for events in events_by_trace.values()
        for event in events
        if event["kind"] in MODEL_SPAN_KINDS
    ]
    replan_events = [
        event
        for events in events_by_trace.values()
        for event in events
        if event["kind"] == "tool.replan_mission"
    ]
    metrics_events = [
        event
        for events in events_by_trace.values()
        for event in events
        if event["kind"] == "tool.get_operation_metrics"
    ]
    expected_calls = len(trace_paths) * len(MODEL_TOOLS)
    if len(model_events) != expected_calls:
        raise ValueError("live model-call count is incomplete")
    if len(replan_events) != len(trace_paths) or len(metrics_events) != len(trace_paths):
        raise ValueError("every live trace must contain replan and operation-metrics spans")
    if {
        event["payload"]["tool_name"] for event in model_events
    } != MODEL_TOOLS:
        raise ValueError("live model-call tool set is incomplete")

    input_tokens = [int(event["payload"]["input_tokens"]) for event in model_events]
    output_tokens = [int(event["payload"]["output_tokens"]) for event in model_events]
    model_latencies = [float(event["payload"]["latency_ms"]) for event in model_events]
    replan_latencies = [float(event["payload"]["latency_ms"]) for event in replan_events]
    request_ids = [str(event["payload"]["request_id"]) for event in model_events]
    if len(request_ids) != len(set(request_ids)):
        raise ValueError("live model request IDs are not unique")

    prompt_rate = float(pricing["pricing_usd_per_token"]["prompt"])
    completion_rate = float(pricing["pricing_usd_per_token"]["completion"])
    per_trace_costs: list[float] = []
    for events in events_by_trace.values():
        calls = [event for event in events if event["kind"] in MODEL_SPAN_KINDS]
        cost = sum(
            int(event["payload"]["input_tokens"]) * prompt_rate
            + int(event["payload"]["output_tokens"]) * completion_rate
            for event in calls
        )
        per_trace_costs.append(cost)

    representative_path = trace_paths[0]
    representative_events = events_by_trace[representative_path]
    representative_calls = [
        {
            "span_kind": event["kind"],
            "provider": event["payload"]["provider"],
            "model": event["payload"]["model"],
            "request_id": event["payload"]["request_id"],
            "http_status": event["payload"]["http_status"],
            "finish_reason": event["payload"]["finish_reason"],
            "tool_name": event["payload"]["tool_name"],
            "tool_arguments_hash": event["payload"]["tool_arguments_hash"],
            "tool_result_hash": event["payload"]["tool_result_hash"],
            "input_tokens": event["payload"]["input_tokens"],
            "output_tokens": event["payload"]["output_tokens"],
            "latency_ms": event["payload"]["latency_ms"],
            "retry_count": event["payload"]["retry_count"],
            "repair_count": event["payload"]["repair_count"],
            "completed_at": event["payload"]["completed_at"],
        }
        for event in representative_events
        if event["kind"] in MODEL_SPAN_KINDS
    ]
    representative_replan = next(
        event["payload"]
        for event in representative_events
        if event["kind"] == "tool.replan_mission"
    )

    agent_path = root / "src/shiftzero/agent.py"
    tool_catalog_path = root / "schemas/tool-catalog.json"
    safety_policy_path = root / "schemas/safety-policy.json"
    prompt_matches_commit = _matches_commit(
        root, gate["git_commit"], "src/shiftzero/agent.py"
    )
    schema_matches_commit = _matches_commit(
        root, gate["git_commit"], "schemas/tool-catalog.json"
    )
    if not prompt_matches_commit or not schema_matches_commit:
        raise ValueError("prompt contract or tool schema no longer matches the tested commit")
    report: dict[str, Any] = {
        "summary_version": "live-runtime-v1",
        "generated_at": pricing["captured_at"],
        "evidence_class": "live_provider_with_reference_simulator",
        "claim_scope": "live_nebius_model_calls_and_reference_simulator_no_physical_hardware",
        "metadata": {
            "provider": gate["provider"],
            "model": gate["model"],
            "endpoint_base_url": pricing["endpoint_base_url"],
            "endpoint_region": pricing["endpoint_region"],
            "tested_git_commit": gate["git_commit"],
            "tested_source_tree_hash": gate["source_tree_hash"],
            "prompt_contract": {
                "version": f"nemotron-forced-tools@{gate['git_commit'][:12]}",
                "path": "src/shiftzero/agent.py",
                "sha256": _sha256(agent_path),
                "matches_tested_commit": prompt_matches_commit,
            },
            "tool_schema": {
                "version": "tools-v3",
                "path": "schemas/tool-catalog.json",
                "sha256": _sha256(tool_catalog_path),
                "matches_tested_commit": schema_matches_commit,
            },
            "safety_policy": {
                "version": "safety-v2",
                "path": "schemas/safety-policy.json",
                "sha256": _sha256(safety_policy_path),
            },
            "map_sha256": gate["map_hash"],
        },
        "compatibility": {
            "official_gate_passed": gate["official_gate_passed"],
            "live_run_count": len(trace_paths),
            "model_call_count": len(model_events),
            "unique_request_id_count": len(set(request_ids)),
            "http_200_count": sum(
                event["payload"]["http_status"] == 200 for event in model_events
            ),
            "tool_call_finish_count": sum(
                event["payload"]["finish_reason"] == "tool_calls"
                for event in model_events
            ),
            "retry_count": sum(event["payload"]["retry_count"] for event in model_events),
            "repair_count": sum(event["payload"]["repair_count"] for event in model_events),
            "all_trace_chains_valid": True,
            "gate_report_hash": gate["report_hash"],
        },
        "measurements": {
            "model_calls": {
                "sample_size": len(model_events),
                "latency_ms": {
                    "median": round(_percentile(model_latencies, 0.5), 6),
                    "p95": round(_percentile(model_latencies, 0.95), 6),
                    "maximum": round(max(model_latencies), 6),
                },
                "input_tokens": sum(input_tokens),
                "output_tokens": sum(output_tokens),
            },
            "replan_mission": {
                "measurement_scope": (
                    "deterministic planner inside live-provider reference-simulator runs"
                ),
                "sample_size": len(replan_latencies),
                "latency_ms": {
                    "median": round(_percentile(replan_latencies, 0.5), 6),
                    "p95": round(_percentile(replan_latencies, 0.95), 6),
                    "maximum": round(max(replan_latencies), 6),
                },
                "successful_result_count": sum(
                    event["payload"]["error"] is None
                    and bool(event["payload"]["result"]["nodes"])
                    for event in replan_events
                ),
            },
            "cost_kpi": {
                "measurement_kind": "measured_tokens_x_captured_catalog_list_price_not_invoice",
                "currency": "USD",
                "catalog_source": pricing["source_url"],
                "catalog_captured_at": pricing["captured_at"],
                "prompt_usd_per_million_tokens": round(prompt_rate * 1_000_000, 6),
                "completion_usd_per_million_tokens": round(
                    completion_rate * 1_000_000, 6
                ),
                "total_gate_estimated_usd": round(sum(per_trace_costs), 9),
                "per_mission_estimated_usd": {
                    "median": round(_percentile(per_trace_costs, 0.5), 9),
                    "p95": round(_percentile(per_trace_costs, 0.95), 9),
                    "maximum": round(max(per_trace_costs), 9),
                },
            },
        },
        "representative_live_trace": {
            "trace_id": representative_events[0]["trace_id"],
            "trace_jsonl_path": representative_path.relative_to(root).as_posix(),
            "trace_jsonl_sha256": _sha256(representative_path),
            "model_calls": representative_calls,
            "replan": {
                "arguments": representative_replan["arguments"],
                "arguments_hash": representative_replan["arguments_hash"],
                "result": representative_replan["result"],
                "result_hash": representative_replan["result_hash"],
                "latency_ms": representative_replan["latency_ms"],
            },
        },
        "limitations": [
            (
                "Model calls are live Nebius Token Factory receipts; motion is the "
                "reference simulator."
            ),
            (
                "Cost is calculated from measured tokens and a captured catalog list price, "
                "not an invoice."
            ),
            "Prompt and schema hashes bind the files that match the tested Git commit.",
        ],
    }
    report["report_hash"] = canonical_hash(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report
