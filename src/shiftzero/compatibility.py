from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from shiftzero.adapters import SimulatorAdapter
from shiftzero.agent import IntentProposalProvider, TokenFactoryProvider
from shiftzero.config import TokenFactorySettings
from shiftzero.domain import (
    ApprovalToken,
    Mission,
    MissionIntent,
    MissionStatus,
    TransportProposal,
    canonical_hash,
)
from shiftzero.evaluation import _git_commit, _source_tree_hash
from shiftzero.safety import SafetyEngine
from shiftzero.simulator import (
    DeterministicPlanner,
    HeroScenario,
    ReferenceWorld,
    load_compatibility_manifest,
)
from shiftzero.workflow import WorkflowController


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return math.inf
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def run_compatibility_gate(
    *,
    scenario: HeroScenario,
    provider: IntentProposalProvider,
    evidence_root: Path,
    report_path: Path,
    repetitions: int = 20,
) -> dict[str, Any]:
    manifest = load_compatibility_manifest()
    variants: list[str] = manifest["intent_variants"]
    latencies: list[float] = []
    completed = 0
    first_schema_valid = 0
    after_repair_valid = 0
    max_consecutive = 0
    current_consecutive = 0
    failures: list[dict[str, str | int]] = []

    for variant_index, text in enumerate(variants):
        for repetition in range(repetitions):
            controller = WorkflowController(
                scenario=scenario,
                provider=provider,
                evidence_root=evidence_root,
            )
            try:
                result = controller.run_hero(operator_text=text)
                completed += 1
                after_repair_valid += 1
                if all(call.repair_count == 0 for call in result.model_calls):
                    first_schema_valid += 1
                latencies.append(sum(call.latency_ms for call in result.model_calls[:2]) / 1000)
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            except Exception as exc:  # Gate must record and continue across the full matrix.
                current_consecutive = 0
                failures.append(
                    {
                        "variant_index": variant_index,
                        "repetition": repetition,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    requested = len(variants) * repetitions
    fault_controls = {
        **evaluate_fault_controls(scenario),
        **evaluate_transport_fault_controls(),
    }
    metrics = {
        "requested_runs": requested,
        "completed_runs": completed,
        "first_schema_valid_rate": first_schema_valid / requested,
        "post_repair_schema_valid_rate": after_repair_valid / requested,
        "wrong_entity_dispatch_count": fault_controls["wrong_entity_dispatch_count"],
        "duplicate_mission_count": fault_controls["duplicate_mission_count"],
        "stale_proposal_execution_count": fault_controls["stale_proposal_execution_count"],
        "hero_max_consecutive_successes": max_consecutive,
        "intent_to_proposal_p95_seconds": round(percentile(latencies, 0.95), 6),
        "intent_to_proposal_median_seconds": round(percentile(latencies, 0.5), 6),
        "measurement": {
            "sample_size": requested,
            "unit": "seconds",
            "method": "parse_intent latency plus propose_transport latency; recovery excluded",
        },
    }
    thresholds = manifest["hard_thresholds"]
    thresholds_passed = {
        "first_schema_valid": metrics["first_schema_valid_rate"]
        >= thresholds["first_schema_valid_rate"],
        "post_repair_schema_valid": metrics["post_repair_schema_valid_rate"]
        >= thresholds["post_repair_schema_valid_rate"],
        "wrong_entity_dispatch": metrics["wrong_entity_dispatch_count"]
        == thresholds["wrong_entity_dispatch_count"],
        "duplicate_mission": metrics["duplicate_mission_count"]
        == thresholds["duplicate_mission_count"],
        "stale_proposal_execution": metrics["stale_proposal_execution_count"]
        == thresholds["stale_proposal_execution_count"],
        "hero_consecutive": metrics["hero_max_consecutive_successes"]
        >= thresholds["hero_consecutive_successes"],
        "intent_to_proposal_p95": metrics["intent_to_proposal_p95_seconds"]
        <= thresholds["intent_to_proposal_p95_seconds"],
        "timeout_failed_closed": fault_controls["timeout_failed_closed"],
        "http_429_bounded_retry": fault_controls["http_429_bounded_retry"],
    }
    real_provider = provider.provider_name == "nebius_token_factory"
    root = Path(__file__).resolve().parents[2]
    report: dict[str, Any] = {
        "gate_version": "compat-v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(root),
        "source_tree_hash": _source_tree_hash(root),
        "manifest_hash": canonical_hash(manifest),
        "map_hash": canonical_hash(scenario.map),
        "provider": provider.provider_name,
        "model": provider.model_name,
        "real_provider": real_provider,
        "metrics": metrics,
        "thresholds": thresholds,
        "thresholds_passed": thresholds_passed,
        "fault_controls": fault_controls,
        "failures": failures,
        "all_thresholds_passed": all(thresholds_passed.values()),
        "claims_boundary": (
            "Fixture reports are preflight evidence only; official status requires the live "
            "nebius_token_factory provider."
        ),
    }
    report["official_gate_passed"] = bool(real_provider and report["all_thresholds_passed"])
    report["report_hash"] = canonical_hash(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def evaluate_fault_controls(scenario: HeroScenario) -> dict[str, Any]:
    planner = DeterministicPlanner()
    safety = SafetyEngine()
    world = ReferenceWorld(scenario.model_copy(deep=True))
    snapshot = world.snapshot()
    intent = MissionIntent(
        pallet_id="P-104",
        source="INBOUND-01",
        destination="RACK-A12",
        constraints=["avoid-human-zone"],
    )
    plan = planner.plan(intent=intent, snapshot=snapshot)
    proposal = TransportProposal.issue(
        proposal_id="TP-FAULT-CONTROL",
        intent=intent,
        plan=plan,
        snapshot_id=snapshot.snapshot_id,
        evidence_refs=["snapshot:test", "location:test"],
    )

    newer_snapshot = world.snapshot()
    stale_proof = safety.verify(
        intent=intent,
        plan=plan,
        snapshot=newer_snapshot,
        proposal=proposal,
    )
    stale_executions = 0 if not stale_proof.passed else 1

    invalid_intent = intent.model_copy(update={"pallet_id": "P-999"})
    invalid_proof = safety.verify(
        intent=invalid_intent,
        plan=plan,
        snapshot=snapshot,
        proposal=proposal,
    )
    wrong_entity_dispatches = 0 if not invalid_proof.passed else 1

    approval = ApprovalToken.issue(
        proposal_hash=proposal.proposal_hash,
        goal_hash=intent.goal_hash,
        actor="fault-test",
    )
    if not approval.valid_for(proposal):
        raise RuntimeError("fault-control setup produced an invalid approval")
    mission = Mission(
        mission_id="M-IDEMPOTENCY-TEST",
        proposal_id=proposal.proposal_id,
        proposal_hash=proposal.proposal_hash,
        goal_hash=intent.goal_hash,
        pallet_id=intent.pallet_id,
        source=intent.source,
        destination=intent.destination,
        selected_agv=plan.selected_agv,
        route=plan.nodes,
        route_version=plan.route_version,
        map_version=plan.map_version,
        snapshot_id=snapshot.snapshot_id,
        proof_hash=invalid_proof.proof_hash,
        status=MissionStatus.APPROVED,
        idempotency_key="dispatch:fixed-test-key",
    )
    adapter = SimulatorAdapter(world)
    first = adapter.start(mission)
    second = adapter.start(mission)
    duplicate_missions = (
        0 if first.mission_id == second.mission_id and adapter.mission_count == 1 else 1
    )

    return {
        "stale_snapshot_blocked": not stale_proof.passed,
        "invalid_entity_blocked": not invalid_proof.passed,
        "duplicate_dispatch_idempotent": duplicate_missions == 0,
        "stale_proposal_execution_count": stale_executions,
        "wrong_entity_dispatch_count": wrong_entity_dispatches,
        "duplicate_mission_count": duplicate_missions,
    }


def evaluate_transport_fault_controls() -> dict[str, bool]:
    intent_arguments = {
        "pallet_id": "P-104",
        "source": "INBOUND-01",
        "destination": "RACK-A12",
        "requested_agv": None,
        "constraints": ["avoid-human-zone"],
    }

    timeout_calls = 0

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        nonlocal timeout_calls
        timeout_calls += 1
        raise httpx.ReadTimeout("compatibility injection", request=request)

    timeout_settings = TokenFactorySettings(api_key="injected", max_retries=1)
    timeout_provider = TokenFactoryProvider(
        timeout_settings,
        client=httpx.Client(
            base_url=timeout_settings.base_url,
            transport=httpx.MockTransport(timeout_handler),
        ),
    )
    timeout_failed_closed = False
    try:
        timeout_provider.parse_intent("Move P-104 from INBOUND-01 to RACK-A12")
    except RuntimeError:
        timeout_failed_closed = timeout_calls == 2

    rate_calls = 0
    idempotency_keys: list[str | None] = []

    def rate_handler(request: httpx.Request) -> httpx.Response:
        nonlocal rate_calls
        rate_calls += 1
        idempotency_keys.append(request.headers.get("idempotency-key"))
        if rate_calls == 1:
            return httpx.Response(429, request=request, json={"error": "injected"})
        return httpx.Response(
            200,
            request=request,
            headers={"x-request-id": "compat-rate-limit"},
            json={
                "id": "compat-rate-limit",
                "model": timeout_settings.model,
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call-compat",
                                    "type": "function",
                                    "function": {
                                        "name": "parse_mission_intent",
                                        "arguments": json.dumps(intent_arguments),
                                    },
                                }
                            ]
                        },
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    rate_provider = TokenFactoryProvider(
        timeout_settings,
        client=httpx.Client(
            base_url=timeout_settings.base_url,
            transport=httpx.MockTransport(rate_handler),
        ),
    )
    _, evidence = rate_provider.parse_intent("Move P-104 from INBOUND-01 to RACK-A12")
    rate_retry_ok = (
        evidence.retry_count == 1
        and rate_calls == 2
        and len(idempotency_keys) == 2
        and idempotency_keys[0] == idempotency_keys[1]
    )
    return {
        "timeout_failed_closed": timeout_failed_closed,
        "http_429_bounded_retry": rate_retry_ok,
    }
