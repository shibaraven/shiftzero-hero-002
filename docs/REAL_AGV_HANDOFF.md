# Real AGV integration handoff

The code intentionally refuses to open the real adapter before a genuine Token Factory report
passes all Compatibility Gate thresholds. Once that attestation exists, hardware work still
requires the following site-owned inputs:

1. AGV/OEM protocol and supported VDA5050 version or MQTT message contract.
2. Broker endpoint, certificate provisioning, topic ACLs, and test serial number.
3. PLC or edge-controller stop interface with a measured local timestamp source.
4. Controlled test map, forbidden zones, speed limits, and emergency-stop procedure.
5. Named safety owner approving the test window and recovery behavior.

Cloud loss, MQTT disconnect, stale telemetry, or reconnect must keep the vehicle stopped. The
real adapter accepts an approved structured mission only and never accepts natural-language or
raw model output.

