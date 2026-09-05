from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from shiftzero.domain import OperationMetrics, canonical_hash
from shiftzero.evidence import EvidenceRecorder


def build_hero_summary(*, root: Path, output_path: Path) -> dict[str, Any]:
    reliability_path = root / "evidence" / "hero-reliability" / "report.json"
    reliability = json.loads(reliability_path.read_text(encoding="utf-8"))
    if not reliability["runs"]:
        raise ValueError("hero reliability report contains no runs")
    trace_path = root / reliability["runs"][0]["trace_path"]
    if not trace_path.is_file():
        raise FileNotFoundError(f"hero trace does not exist: {trace_path}")
    if not EvidenceRecorder.verify(trace_path):
        raise ValueError("hero trace hash chain is invalid")
    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    intent = _payload(events, "intent.typed")
    proposal = _payload(events, "proposal.created")
    proof = _payload(events, "safety.proof")
    approval = _payload(events, "approval.granted")
    initial_plan = _payload(events, "tool.plan_transport")["result"]
    replan = _payload(events, "tool.replan_mission")["result"]
    stop = _payload(events, "execution.local_stop")
    outcome_event = _event(events, "outcome.completed")
    outcome = outcome_event["payload"]
    operation_metrics = OperationMetrics.model_validate(
        _payload(events, "tool.get_operation_metrics")["result"]
    )
    model_calls = [
        event["payload"]
        for event in events
        if event["kind"] in {"llm.intent", "llm.proposal", "llm.recovery"}
    ]
    policy_path = root / "schemas" / "safety-policy.json"
    trace_relative = trace_path.resolve().relative_to(root.resolve()).as_posix()
    body: dict[str, Any] = {
        "summary_version": "hero-summary-v3",
        "measurement_scope": "reference_simulator_fixture_provider",
        "official_gate_passed": False,
        "evidence_captured_at": outcome_event["recorded_at"],
        "intent": intent,
        "proposal_id": proposal["proposal_id"],
        "mission_id": outcome["mission_id"],
        "selected_agv": proposal["selected_agv"],
        "initial_route": initial_plan["nodes"],
        "initial_route_version": initial_plan["route_version"],
        "replan_route": replan["nodes"],
        "replan_route_version": replan["route_version"],
        "safety_proof_id": proof["proof_id"],
        "safety_proof_hash": proof["proof_hash"],
        "safety_policy_version": proof["policy_version"],
        "safety_policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "approval": {
            "token_id": approval["token_id"],
            "actor": approval["actor"],
            "issued_at": approval["issued_at"],
            "expires_at": approval["expires_at"],
        },
        "stop_latency_ms": stop["latency_ms"],
        "stop_latency_kind": stop["measurement_kind"],
        "total_duration_ms": outcome["total_duration_ms"],
        "human_interventions": outcome["human_interventions"],
        "estimated_model_cost_usd": outcome["estimated_model_cost_usd"],
        "operation_metrics": operation_metrics,
        "final_node": outcome["final_node"],
        "final_pose": outcome["final_pose"],
        "destination_occupancy": outcome["destination_occupancy"],
        "final_status": "COMPLETED",
        "trace_id": events[0]["trace_id"],
        "trace_path": trace_relative,
        "trace_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest(),
        "trace_chain_valid": True,
        "state_history": [
            event["payload"]["state"]
            for event in events
            if event["kind"] == "workflow.transition"
        ],
        "model_calls": model_calls,
        "claims_boundary": (
            "All values come from a deterministic fixture/reference-simulator trace. "
            "No physical stop-latency or live Nebius claim is made."
        ),
    }
    body["summary_hash"] = canonical_hash(body)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return body


def _payload(events: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return _event(events, kind)["payload"]


def _event(events: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    try:
        return next(event for event in events if event["kind"] == kind)
    except StopIteration as exc:
        raise ValueError(f"hero trace is missing {kind}") from exc
