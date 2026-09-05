# Frozen HERO-002 safety rules

| Check | Pass condition | Failure behavior |
|---|---|---|
| Entity validity | Pallet, source, destination, and AGV exist in the live snapshot | Reject |
| Map consistency | Proposal map version equals the live map version | Re-observe and replan |
| Battery reserve | Estimated post-mission battery is at least 20% | Choose another AGV or reject |
| Forbidden zone | No route node is in a forbidden or human-only zone | Reject route |
| Collision | No route node or edge intersects an active obstacle | Replan |
| Deadlock | Required reservation groups are available without cyclic wait | Queue or replan |
| Destination occupancy | Destination is empty or already contains the requested pallet | Hold |
| Approval integrity | Token is valid, unexpired, and bound to the proposal hash and actor | Do not execute |

Policy version: `safety-v1`. Failure is closed by default. Unknown or stale data never becomes a
pass. The local stop path is independent of the cloud and has priority over mission completion.

