from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from shiftzero.domain import canonical_hash

OFFICIAL_RULES_URL = "https://nebiusglobalaihackathon.devpost.com/rules"
SESSION_ID = "SIM-A06A07-REFERENCE-001"
TRACE_ID = "SIM-TRACE-A06A07-001"
MISSION_ID = "SIM-MISSION-P104-A12"


def build_competition_simulation_evidence(
    *,
    output_path: Path,
    base_time: datetime | None = None,
    sensor_to_stop_ms: int = 150,
) -> dict[str, Any]:
    """Build deterministic A06/A07 Digital Twin evidence for the no-hardware track.

    This artifact is usable as a demonstration of the key application modules under the
    competition's explicit no-hardware provision. It never represents synthetic timing as a
    physical measurement and therefore cannot pass the separate physical-field validator.
    """
    if not 1 <= sensor_to_stop_ms <= 1000:
        raise ValueError("sensor_to_stop_ms must be between 1 and 1000")

    started_at = (base_time or datetime.now(UTC)).astimezone(UTC)
    event_specs = [
        (0, "mission.started", "dispatch.simulator", "AGV-03 accepted route sim-route-a"),
        (
            2600,
            "network.cloud_disconnected",
            "network.fixture",
            "Cloud route removed before obstacle injection; edge controller remains active",
        ),
        (
            2900,
            "sensor.raw_detected",
            "lidar.fixture",
            "Synthetic return entered the detection envelope",
        ),
        (
            3000,
            "sensor.filtered_obstacle",
            "edge.fixture",
            "Synthetic obstacle confirmed at N09",
        ),
        (
            3012,
            "edge.stop_issued",
            "edge.fixture",
            "Local stop issued while the cloud route is disconnected",
        ),
        (
            3000 + sensor_to_stop_ms,
            "agv.stationary_confirmed",
            "agv-03.fixture",
            f"Synthetic stationary confirmation ({sensor_to_stop_ms} ms)",
        ),
        (
            3000 + sensor_to_stop_ms + 850,
            "replan.accepted",
            "planner.fixture",
            "Route version sim-route-a -> sim-route-b",
        ),
        (
            3000 + sensor_to_stop_ms + 1750,
            "mission.resumed",
            "dispatch.simulator",
            "AGV-03 resumed on the verified detour",
        ),
        (
            3000 + sensor_to_stop_ms + 4700,
            "mission.completed",
            "agv-03.fixture",
            "P-104 reached N12 with final pose captured",
        ),
    ]
    events = [
        {
            "sequence": index,
            "timestamp": (started_at + timedelta(milliseconds=at_ms)).isoformat(),
            "elapsed_ms": at_ms,
            "kind": kind,
            "source": source,
            "session_id": SESSION_ID,
            "trace_id": TRACE_ID,
            "correlation_id": SESSION_ID,
            "mission_id": MISSION_ID,
            "detail": detail,
        }
        for index, (at_ms, kind, source, detail) in enumerate(event_specs, start=1)
    ]
    event_order = [event["kind"] for event in events]
    cloud_disconnect_precedes_detection = event_order.index(
        "network.cloud_disconnected"
    ) < event_order.index("sensor.filtered_obstacle")
    local_stop_without_cloud = cloud_disconnect_precedes_detection and event_order.index(
        "edge.stop_issued"
    ) < event_order.index("agv.stationary_confirmed")
    a06_passed = sensor_to_stop_ms <= 200 and local_stop_without_cloud
    required_a07_order = [
        "sensor.filtered_obstacle",
        "edge.stop_issued",
        "agv.stationary_confirmed",
        "replan.accepted",
        "mission.resumed",
        "mission.completed",
    ]
    a07_passed = [event_order.index(kind) for kind in required_a07_order] == sorted(
        event_order.index(kind) for kind in required_a07_order
    )

    report: dict[str, Any] = {
        "schema_version": "competition-simulation-evidence-v1",
        "evidence_class": "digital_twin_simulation",
        "claim_scope": "official_competition_no_hardware_path",
        "generated_at": datetime.now(UTC).isoformat(),
        "official_rule_basis": {
            "url": OFFICIAL_RULES_URL,
            "checked_at": datetime.now(UTC).isoformat(),
            "interpretation": (
                "Physical AI entries without physical hardware may demonstrate the key "
                "application modules in action."
            ),
        },
        "eligibility": {
            "competition_submission_usable_without_hardware": True,
            "physical_hardware_claimed": False,
            "physical_measurement_claimed": False,
            "passes_internal_physical_field_gate": False,
        },
        "identifiers": {
            "session_id": SESSION_ID,
            "trace_id": TRACE_ID,
            "correlation_id": SESSION_ID,
            "mission_id": MISSION_ID,
            "vehicle_id": "AGV-03",
            "pallet_id": "P-104",
        },
        "simulator": {
            "name": "ShiftZero A06/A07 Digital Twin Lab",
            "vehicle_count": 9,
            "clock": "deterministic_synthetic_elapsed_time",
            "cloud_mode": "disconnected_before_obstacle",
            "sensor_to_stationary_ms": sensor_to_stop_ms,
        },
        "assertions": {
            "a06_simulation_passed": a06_passed,
            "a06_cloud_disconnect_precedes_detection": cloud_disconnect_precedes_detection,
            "a06_local_stop_without_cloud": local_stop_without_cloud,
            "a06_sensor_to_stationary_at_most_200_ms": sensor_to_stop_ms <= 200,
            "a07_simulation_passed": a07_passed,
            "a07_synchronized_sequence_complete": a07_passed,
            "a07_route_version_changed": True,
            "a07_final_pose_present": True,
        },
        "outcome": {
            "status": "COMPLETED",
            "route_version_before": "sim-route-a",
            "route_version_after": "sim-route-b",
            "final_pose": {"node_id": "N12", "x": 842, "y": 135, "heading_deg": 315},
        },
        "events": events,
        "limitations": [
            "All sensor, network, vehicle, timing and motion data in this artifact are synthetic.",
            "This artifact demonstrates application behavior, not real AGV performance.",
            "It must not be submitted or described as physical sensor-to-stop evidence.",
        ],
    }
    report["passed"] = a06_passed and a07_passed
    report["report_hash"] = canonical_hash(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def verify_competition_simulation_evidence(report: dict[str, Any]) -> bool:
    """Verify the report hash and the explicit synthetic-claim boundary."""
    body = dict(report)
    stored_hash = body.pop("report_hash", None)
    assertions = body.get("assertions", {})
    eligibility = body.get("eligibility", {})
    return bool(
        stored_hash == canonical_hash(body)
        and report.get("evidence_class") == "digital_twin_simulation"
        and report.get("claim_scope") == "official_competition_no_hardware_path"
        and report.get("passed") is True
        and assertions.get("a06_simulation_passed") is True
        and assertions.get("a07_simulation_passed") is True
        and eligibility.get("competition_submission_usable_without_hardware") is True
        and eligibility.get("physical_hardware_claimed") is False
        and eligibility.get("physical_measurement_claimed") is False
        and eligibility.get("passes_internal_physical_field_gate") is False
    )
