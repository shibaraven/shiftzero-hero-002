from __future__ import annotations

import hashlib
import json
from pathlib import Path

from shiftzero.physical_evidence import validate_physical_evidence

ARTIFACT_CONTENT = {
    "continuous-video.mp4": b"physical-video-fixture",
    "telemetry.jsonl": b"physical-telemetry-fixture",
    "sensor-capture.jsonl": b"physical-sensor-fixture",
    "vda5050-trace.jsonl": b"physical-vda5050-fixture",
}


def _artifact(path: str) -> dict[str, object]:
    content = ARTIFACT_CONTENT[path]
    return {
        "path": path,
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _write_artifacts(root: Path) -> None:
    for name, content in ARTIFACT_CONTENT.items():
        (root / name).write_bytes(content)


def _physical_payload() -> dict[str, object]:
    events = [
        ("mission.started", "2026-09-20T01:00:00.000Z", "mission-controller"),
        ("sensor.raw_detected", "2026-09-20T01:00:02.900Z", "e1r"),
        ("sensor.filtered_obstacle", "2026-09-20T01:00:03.000Z", "edge-safety"),
        ("edge.stop_issued", "2026-09-20T01:00:03.012Z", "edge-safety"),
        ("agv.stationary_confirmed", "2026-09-20T01:00:03.084Z", "agv-03"),
        ("replan.accepted", "2026-09-20T01:00:04.500Z", "mission-controller"),
        ("mission.resumed", "2026-09-20T01:00:05.000Z", "operator"),
        ("mission.completed", "2026-09-20T01:00:10.000Z", "agv-03"),
    ]
    return {
        "schema_version": "physical-field-evidence-v1",
        "evidence_class": "physical_field_test",
        "claim_scope": "a06_a07_physical_validation",
        "final_submission_eligible": True,
        "session": {
            "session_id": "FIELD-001",
            "trace_id": "TR-FIELD-001",
            "mission_id": "M-001",
            "started_at": "2026-09-20T01:00:00.000Z",
            "completed_at": "2026-09-20T01:00:10.000Z",
        },
        "hardware": {
            "agv_id": "AGV-03",
            "protocol": "VDA5050 over MQTT",
            "sensor": "RoboSense E1R",
            "edge_controller": "edge-gateway-01",
            "stop_interface": "PLC safety input",
            "test_area": "controlled-test-zone-a",
        },
        "clock": {
            "source": "PTP grandmaster",
            "synchronized": True,
            "maximum_skew_ms": 2.0,
        },
        "events": [
            {
                "sequence": index,
                "kind": kind,
                "timestamp": timestamp,
                "source": source,
                "correlation_id": "FIELD-001",
            }
            for index, (kind, timestamp, source) in enumerate(events, 1)
        ],
        "measurements": {
            "sensor_to_stop_ms": 84.0,
            "local_path_only": True,
            "cloud_disconnected_stop_verified": True,
            "route_version_before": "route-v17",
            "route_version_after": "route-v18",
            "final_pose": {"node_id": "N12", "x": 6.0, "y": 0.0, "heading_deg": 315.0},
        },
        "artifacts": {
            "continuous_video": _artifact("continuous-video.mp4"),
            "telemetry": _artifact("telemetry.jsonl"),
            "sensor_capture": _artifact("sensor-capture.jsonl"),
            "mqtt_or_vda5050_trace": _artifact("vda5050-trace.jsonl"),
        },
        "attestation": {
            "safety_owner": "Site Safety Owner",
            "role": "safety_manager",
            "signed_at": "2026-09-20T01:01:00.000Z",
            "test_window_approved": True,
        },
    }


def test_physical_evidence_passes_with_correlated_local_stop(tmp_path: Path) -> None:
    evidence = tmp_path / "physical.json"
    _write_artifacts(tmp_path)
    evidence.write_text(json.dumps(_physical_payload()), encoding="utf-8")

    report = validate_physical_evidence(input_path=evidence)

    assert report["passed"] is True
    assert report["a06_sensor_to_stop_passed"] is True
    assert report["a07_physical_loop_passed"] is True
    assert report["measured_sensor_to_stop_ms"] == 84.0
    assert report["artifact_files_verified"] == 4


def test_simulator_rehearsal_cannot_pass_as_physical_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "rehearsal.json"
    payload = _physical_payload()
    payload["evidence_class"] = "simulator_rehearsal"
    payload["final_submission_eligible"] = False
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_physical_evidence(input_path=evidence)

    assert report["passed"] is False
    assert report["a06_sensor_to_stop_passed"] is False
    assert report["a07_physical_loop_passed"] is False


def test_physical_evidence_rejects_timestamp_mismatch(tmp_path: Path) -> None:
    evidence = tmp_path / "mismatch.json"
    _write_artifacts(tmp_path)
    payload = _physical_payload()
    payload["measurements"]["sensor_to_stop_ms"] = 40.0
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_physical_evidence(input_path=evidence)

    assert report["passed"] is False
    assert "declared sensor_to_stop_ms" in " ".join(report["errors"])


def test_physical_evidence_rejects_tampered_artifact(tmp_path: Path) -> None:
    evidence = tmp_path / "tampered.json"
    _write_artifacts(tmp_path)
    evidence.write_text(json.dumps(_physical_payload()), encoding="utf-8")
    (tmp_path / "telemetry.jsonl").write_bytes(b"tampered")

    report = validate_physical_evidence(input_path=evidence)

    assert report["passed"] is False
    assert report["artifact_files_verified"] == 3
    assert "telemetry byte count" in " ".join(report["errors"])
