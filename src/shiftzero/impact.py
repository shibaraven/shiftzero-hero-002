from __future__ import annotations

import json
import math
import random
from pathlib import Path
from statistics import median
from typing import Any

from shiftzero.domain import canonical_hash, utc_now
from shiftzero.simulator import HeroScenario

MODEL_VERSION = "warehouse-impact-load-v1"
DEFAULT_DAILY_LOADS = (400, 450, 500)


def run_impact_load_model(
    *,
    scenario: HeroScenario,
    output_path: Path,
    sample_days: int = 20,
    daily_loads: tuple[int, ...] = DEFAULT_DAILY_LOADS,
) -> dict[str, Any]:
    """Project warehouse load using a reproducible, explicitly non-physical queue model."""
    if sample_days < 20:
        raise ValueError("impact load model requires at least 20 simulated days per load")
    if not daily_loads or any(load < 400 or load > 500 for load in daily_loads):
        raise ValueError("daily loads must stay inside the declared 400-500 pallets/day range")

    assumptions = _assumptions(scenario)
    rows = [
        _simulate_load(
            pallets_per_day=load,
            sample_days=sample_days,
            assumptions=assumptions,
        )
        for load in daily_loads
    ]
    model_inputs = {
        "scenario_id": scenario.scenario_id,
        "scenario_sha256": canonical_hash(scenario),
        "assumptions": assumptions,
        "daily_loads": list(daily_loads),
        "sample_days_per_load": sample_days,
    }
    body: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "generated_at": utc_now().isoformat(),
        "measurement_scope": "planning_projection_reference_map_not_physical_measurement",
        "official_or_physical_evidence": False,
        "assumptions_are_not_measurements": True,
        "method": (
            "Seeded discrete-event M/G/2 queue simulation. Each load uses 20 independent "
            "simulated operating days, exponential inter-arrival spacing normalized to one "
            "shift, and +/-15% service-time sensitivity. Operator-touch impact is a direct "
            "calculation from the declared manual and agent assumptions."
        ),
        "inputs": model_inputs,
        "loads": rows,
        "conclusion": {
            "range_evaluated": "400-500 pallets/day",
            "operator_hours_saved_per_day_range": [
                rows[0]["operator_impact"]["hours_saved_per_day"],
                rows[-1]["operator_impact"]["hours_saved_per_day"],
            ],
            "capacity_note": (
                "Two nominal AGVs are modeled. A third AGV is recommended wherever the "
                "80% utilization buffer calculation requires it; validate all assumptions "
                "with site telemetry before making an operational claim."
            ),
        },
    }
    body["model_hash"] = canonical_hash({"inputs": model_inputs, "loads": rows})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return body


def _assumptions(scenario: HeroScenario) -> dict[str, Any]:
    route = ["N01", "N04", "N05", "N10", "N12"]
    edges = {
        frozenset((edge.from_node, edge.to_node)): edge for edge in scenario.map.edges
    }
    travel_seconds = 0.0
    route_distance_m = 0.0
    for start, end in zip(route, route[1:], strict=False):
        edge = edges[frozenset((start, end))]
        route_distance_m += edge.length_m
        travel_seconds += edge.length_m / edge.speed_limit_mps
    pickup_dropoff_seconds = 90.0
    return_and_buffer_seconds = 58.0
    nominal_cycle_seconds = travel_seconds + pickup_dropoff_seconds + return_and_buffer_seconds
    return {
        "operating_hours_per_day": 16,
        "active_agvs": 2,
        "availability_factor": 0.85,
        "hero_replan_route": route,
        "route_distance_m": round(route_distance_m, 3),
        "route_travel_seconds": round(travel_seconds, 3),
        "pickup_dropoff_seconds": pickup_dropoff_seconds,
        "return_and_buffer_seconds": return_and_buffer_seconds,
        "nominal_cycle_seconds": round(nominal_cycle_seconds, 3),
        "service_time_variation_percent": 15,
        "manual_operator_touch_seconds_per_mission": 75,
        "agent_operator_touch_seconds_per_mission": 12,
        "target_max_average_agv_utilization": 0.8,
    }


def _simulate_load(
    *, pallets_per_day: int, sample_days: int, assumptions: dict[str, Any]
) -> dict[str, Any]:
    operating_seconds = assumptions["operating_hours_per_day"] * 3600
    active_agvs = assumptions["active_agvs"]
    effective_cycle = assumptions["nominal_cycle_seconds"] / assumptions["availability_factor"]
    all_waits: list[float] = []
    all_completion_flags: list[bool] = []
    daily_backlogs: list[int] = []
    daily_utilizations: list[float] = []

    for day in range(sample_days):
        rng = random.Random(2002 + pallets_per_day * 100 + day)
        intervals = [rng.expovariate(1.0) for _ in range(pallets_per_day)]
        scale = operating_seconds * 0.985 / sum(intervals)
        arrivals: list[float] = []
        cursor = 0.0
        for interval in intervals:
            cursor += interval * scale
            arrivals.append(cursor)

        available_at = [0.0 for _ in range(active_agvs)]
        used_service_seconds = 0.0
        backlog = 0
        for arrival in arrivals:
            agv_index = min(range(active_agvs), key=available_at.__getitem__)
            service_seconds = effective_cycle * rng.uniform(0.85, 1.15)
            start = max(arrival, available_at[agv_index])
            finish = start + service_seconds
            available_at[agv_index] = finish
            used_service_seconds += service_seconds
            all_waits.append(start - arrival)
            completed = finish <= operating_seconds
            all_completion_flags.append(completed)
            if not completed:
                backlog += 1
        daily_backlogs.append(backlog)
        daily_utilizations.append(used_service_seconds / (active_agvs * operating_seconds))

    manual_touch_hours = (
        pallets_per_day * assumptions["manual_operator_touch_seconds_per_mission"] / 3600
    )
    agent_touch_hours = (
        pallets_per_day * assumptions["agent_operator_touch_seconds_per_mission"] / 3600
    )
    required_agvs = math.ceil(
        pallets_per_day
        * effective_cycle
        / (
            operating_seconds
            * assumptions["target_max_average_agv_utilization"]
        )
    )
    completion_rate = sum(all_completion_flags) / len(all_completion_flags)
    p95_wait = _percentile(all_waits, 0.95)
    return {
        "pallets_per_day": pallets_per_day,
        "sample_days": sample_days,
        "simulated_missions": pallets_per_day * sample_days,
        "agv_metrics": {
            "active_agvs": active_agvs,
            "mean_utilization": round(sum(daily_utilizations) / sample_days, 6),
            "median_queue_wait_seconds": round(median(all_waits), 3),
            "p95_queue_wait_seconds": round(p95_wait, 3),
            "completion_rate_within_operating_day": round(completion_rate, 6),
            "max_end_of_day_backlog": max(daily_backlogs),
            "required_agvs_for_80_percent_buffer": required_agvs,
            "status": (
                "MODELED_CAPACITY_OK"
                if completion_rate >= 0.99 and p95_wait <= 300 and required_agvs <= active_agvs
                else "CAPACITY_BUFFER_RECOMMENDED"
            ),
        },
        "operator_impact": {
            "manual_touch_hours_per_day": round(manual_touch_hours, 3),
            "agent_touch_hours_per_day": round(agent_touch_hours, 3),
            "hours_saved_per_day": round(manual_touch_hours - agent_touch_hours, 3),
            "touch_time_reduction_percent": round(
                (1 - agent_touch_hours / manual_touch_hours) * 100, 1
            ),
            "basis": "declared planning assumptions, not observed site labor",
        },
    }


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)
