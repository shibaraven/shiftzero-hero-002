# A06/A07 field-test protocol

This protocol is only for an optional future physical-performance claim. The official competition
also permits a no-hardware Physical AI entry that demonstrates its key application modules; that
path is completed separately by `evidence/a06-a07-simulation-validation.json`.

The Digital Twin Lab's nine-vehicle traffic, 2D/3D views, blockage injection, simulated stop
latency and downloadable report are always labeled `DIGITAL TWIN / SIMULATION` and `NO PHYSICAL
CLAIM`. They pass the competition simulation assertions but never satisfy this physical validator.

## A06 - local sensor-to-stop measurement

Use one synchronized monotonic clock, preferably PTP, across the sensor, edge gateway and AGV
telemetry recorder. Record these raw events without editing their timestamps:

1. `sensor.raw_detected`
2. `sensor.filtered_obstacle`
3. `edge.stop_issued`
4. `agv.stationary_confirmed`

The acceptance measurement is:

```text
agv.stationary_confirmed - sensor.filtered_obstacle <= 200 ms
```

Repeat the stop test while the public internet/cloud route is disconnected. The edge/PLC stop
path must still work. Record the clock source and maximum measured clock skew; the validator
rejects skew above 20 ms.

## A07 - correlated physical loop

Use one `session_id`, `trace_id`, `mission_id` and correlation ID for the complete take:

1. Start M-001 on the real AGV/AGF.
2. Capture continuous vehicle motion and synchronized telemetry.
3. Place the obstacle at the marked safe location under the safety owner's control.
4. Preserve the raw sensor capture and filtered obstacle event.
5. Stop locally, keep the vehicle stationary, and record the stop source.
6. Produce a different route version and record `replan.accepted`.
7. Resume only under the approved recovery policy.
8. Complete at RACK-A12 and record the final `x`, `y`, heading and node.

The continuous video must visibly show the AGV, obstacle, local stop, resumed movement and final
location. Hash the original video, telemetry, sensor capture and MQTT/VDA5050 trace before any
editing.

## Evidence file

Place the four original artifacts beside the JSON file. Create a JSON file matching
`schemas/physical-field-evidence.schema.json`; every artifact entry contains its relative `path`,
exact byte count and SHA-256. Then run:

```powershell
.\.venv\Scripts\python.exe -m shiftzero.cli validate-physical-evidence `
  --input evidence/physical/field-session.json `
  --output evidence/physical/validation-report.json
```

The validator requires eight correlated events, chronological and unique sequences, a measured
sensor-to-stop result no greater than 200 ms, a changed route version, a final pose, four artifact
files whose actual bytes match their declarations, cloud-disconnected stop proof and a named
safety-owner attestation. Absolute paths and path traversal are rejected. Simulator exports use a
different evidence class and are rejected by design.

## Files to provide after the on-site test

- Original continuous video, plus its SHA-256.
- Sensor raw/filtered event export with the clock source.
- AGV telemetry containing velocity and stationary confirmation.
- MQTT/VDA5050 order, state and instant-action trace.
- Map/test-area version and the two route versions.
- Named safety-owner approval and test-window timestamp.
