# Frozen HERO-002 safety rules

| Check | Pass condition | Failure behavior |
|---|---|---|
| Entity validity | Pallet, source, destination, and AGV exist in the live snapshot | Reject |
| Map consistency | Proposal map version equals the live map version | Re-observe and replan |
| Battery reserve | Estimated post-mission battery is at least 20% | Choose another AGV or reject |
| Vehicle type | Every route node allows the selected AGV vehicle type | Reject route |
| Forbidden zone | No route node is in a forbidden or human-only zone | Reject route |
| Collision | No route node intersects an active obstacle and no reservation time window overlaps another vehicle | Replan |
| Reservation availability | Required reservation groups are not held by another AGV | Queue or replan |
| Deadlock | The selected AGV is not part of a cycle in the live wait-for graph | Queue or abort |
| Destination occupancy | Destination is reachable and empty or already contains the requested pallet | Hold |
| Approval integrity | Token is valid, unexpired, and bound to the proposal hash and actor | Do not execute |

Policy version: `safety-v2`. Failure is closed by default. Unknown or stale data never becomes a
pass. The local stop path is independent of the cloud and has priority over mission completion.
Obstacle TTL is enforced. A confidence of at least 0.9 causes immediate treatment as active;
medium-confidence observations require at least two observations to filter isolated false positives.

The controller records a route-only `safety.route_proof` before human review. After approval, it
issues the execution `safety.proof` with all route checks plus `approval_integrity`; the Mission
stores that final proof hash. Equivalent-route replans repeat the approval-integrity check before
Resume. A missing, changed or expired approval therefore produces a failed proof and no motion.
