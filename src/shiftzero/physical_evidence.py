from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from shiftzero.domain import canonical_hash

SHA256_PATTERN = r"^[a-f0-9]{64}$"


class PhysicalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    kind: Literal[
        "mission.started",
        "sensor.raw_detected",
        "sensor.filtered_obstacle",
        "edge.stop_issued",
        "agv.stationary_confirmed",
        "replan.accepted",
        "mission.resumed",
        "mission.completed",
    ]
    timestamp: datetime
    source: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class PhysicalSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    mission_id: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime


class PhysicalHardware(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agv_id: str = Field(min_length=1)
    protocol: str = Field(min_length=1)
    sensor: str = Field(min_length=1)
    edge_controller: str = Field(min_length=1)
    stop_interface: str = Field(min_length=1)
    test_area: str = Field(min_length=1)


class ClockEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    synchronized: Literal[True]
    maximum_skew_ms: float = Field(ge=0, le=20)


class FinalPhysicalPose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    x: float
    y: float
    heading_deg: float = Field(ge=0, lt=360)


class PhysicalMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sensor_to_stop_ms: float = Field(ge=0, le=200)
    local_path_only: Literal[True]
    cloud_disconnected_stop_verified: Literal[True]
    route_version_before: str = Field(min_length=1)
    route_version_after: str = Field(min_length=1)
    final_pose: FinalPhysicalPose


class PhysicalArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    bytes: int = Field(gt=0)
    sha256: str = Field(pattern=SHA256_PATTERN)


class PhysicalArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    continuous_video: PhysicalArtifactReference
    telemetry: PhysicalArtifactReference
    sensor_capture: PhysicalArtifactReference
    mqtt_or_vda5050_trace: PhysicalArtifactReference


class SafetyAttestation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    safety_owner: str = Field(min_length=1)
    role: str = Field(min_length=1)
    signed_at: datetime
    test_window_approved: Literal[True]


class PhysicalFieldEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["physical-field-evidence-v1"]
    evidence_class: Literal["physical_field_test"]
    claim_scope: Literal["a06_a07_physical_validation"]
    final_submission_eligible: Literal[True]
    session: PhysicalSession
    hardware: PhysicalHardware
    clock: ClockEvidence
    events: list[PhysicalEvent] = Field(min_length=8)
    measurements: PhysicalMeasurements
    artifacts: PhysicalArtifacts
    attestation: SafetyAttestation


REQUIRED_EVENT_KINDS = (
    "mission.started",
    "sensor.raw_detected",
    "sensor.filtered_obstacle",
    "edge.stop_issued",
    "agv.stationary_confirmed",
    "replan.accepted",
    "mission.resumed",
    "mission.completed",
)


def validate_physical_evidence(
    *, input_path: Path, output_path: Path | None = None
) -> dict[str, object]:
    """Validate correlated A06/A07 field evidence and fail closed on rehearsal data."""
    errors: list[str] = []
    measured_sensor_to_stop_ms: float | None = None
    payload: dict[str, object] | None = None
    input_sha256: str | None = None
    artifact_files_verified = 0

    try:
        content = input_path.read_bytes()
        input_sha256 = hashlib.sha256(content).hexdigest()
        raw = json.loads(content)
        payload = PhysicalFieldEvidence.model_validate(raw).model_dump(mode="json")
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        errors.append(str(exc))

    if payload is not None:
        events = payload["events"]
        assert isinstance(events, list)
        by_kind = {event["kind"]: event for event in events}
        missing = [kind for kind in REQUIRED_EVENT_KINDS if kind not in by_kind]
        if missing:
            errors.append(f"required physical events missing: {', '.join(missing)}")

        event_kinds = tuple(event["kind"] for event in events)
        if event_kinds != REQUIRED_EVENT_KINDS:
            errors.append("physical events must contain the required kinds in protocol order")

        sequences = [event["sequence"] for event in events]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            errors.append("event sequence values must be unique and strictly increasing")

        timestamps = [datetime.fromisoformat(event["timestamp"]) for event in events]
        if timestamps != sorted(timestamps):
            errors.append("event timestamps must be chronological")

        if not missing:
            trigger = datetime.fromisoformat(by_kind["sensor.filtered_obstacle"]["timestamp"])
            stationary = datetime.fromisoformat(
                by_kind["agv.stationary_confirmed"]["timestamp"]
            )
            measured_sensor_to_stop_ms = round(
                (stationary - trigger).total_seconds() * 1000, 3
            )
            declared = float(payload["measurements"]["sensor_to_stop_ms"])
            if measured_sensor_to_stop_ms < 0:
                errors.append("stationary confirmation precedes the filtered obstacle event")
            if measured_sensor_to_stop_ms > 200:
                errors.append(
                    f"measured sensor-to-stop latency is {measured_sensor_to_stop_ms} ms (> 200 ms)"
                )
            if abs(measured_sensor_to_stop_ms - declared) > 1:
                errors.append(
                    "declared sensor_to_stop_ms does not match correlated event timestamps"
                )

        measurements = payload["measurements"]
        if measurements["route_version_before"] == measurements["route_version_after"]:
            errors.append("replan must produce a different route version")

        session = payload["session"]
        if session["started_at"] >= session["completed_at"]:
            errors.append("session completed_at must be after started_at")
        if timestamps and (
            timestamps[0] < datetime.fromisoformat(session["started_at"])
            or timestamps[-1] > datetime.fromisoformat(session["completed_at"])
        ):
            errors.append("all physical events must fall inside the declared session window")

        correlation_ids = {event["correlation_id"] for event in events}
        if len(correlation_ids) != 1:
            errors.append("all physical events must share one correlation_id")
        elif next(iter(correlation_ids)) != session["session_id"]:
            errors.append("physical event correlation_id must match session_id")

        source_text = " ".join(
            [event["source"] for event in events]
            + [str(value) for value in payload["hardware"].values()]
        ).lower()
        if "fixture" in source_text or "simulator" in source_text:
            errors.append("physical evidence cannot identify a fixture or simulator source")

        if datetime.fromisoformat(payload["attestation"]["signed_at"]) < datetime.fromisoformat(
            session["completed_at"]
        ):
            errors.append("safety-owner attestation must be signed after the test session")

        artifact_root = input_path.resolve().parent
        for artifact_name, artifact in payload["artifacts"].items():
            artifact_path = Path(artifact["path"])
            if artifact_path.is_absolute():
                errors.append(f"{artifact_name} path must be relative to the evidence JSON")
                continue
            resolved = (artifact_root / artifact_path).resolve()
            if not resolved.is_relative_to(artifact_root):
                errors.append(f"{artifact_name} path leaves the evidence directory")
                continue
            try:
                artifact_content = resolved.read_bytes()
            except OSError as exc:
                errors.append(f"{artifact_name} cannot be read: {exc}")
                continue
            if len(artifact_content) != artifact["bytes"]:
                errors.append(f"{artifact_name} byte count does not match the file")
                continue
            if hashlib.sha256(artifact_content).hexdigest() != artifact["sha256"]:
                errors.append(f"{artifact_name} SHA-256 does not match the file")
                continue
            artifact_files_verified += 1

    report: dict[str, object] = {
        "validator_version": "physical-evidence-validator-v1",
        "input_path": input_path.as_posix(),
        "input_sha256": input_sha256,
        "evidence_class": payload.get("evidence_class") if payload else None,
        "event_count": len(payload["events"]) if payload else 0,
        "artifact_files_verified": artifact_files_verified,
        "measured_sensor_to_stop_ms": measured_sensor_to_stop_ms,
        "a06_sensor_to_stop_passed": payload is not None
        and measured_sensor_to_stop_ms is not None
        and measured_sensor_to_stop_ms <= 200
        and not errors,
        "a07_physical_loop_passed": payload is not None
        and all(
            kind in {event["kind"] for event in payload["events"]}
            for kind in REQUIRED_EVENT_KINDS
        )
        and not errors,
        "errors": errors,
        "passed": payload is not None and artifact_files_verified == 4 and not errors,
    }
    report["report_hash"] = canonical_hash(report)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report
