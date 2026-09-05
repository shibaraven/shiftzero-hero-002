from __future__ import annotations

from dataclasses import dataclass

from shiftzero.domain import (
    AgvState,
    MissionIntent,
    OperationalSnapshot,
    RoutePlan,
    SafetyCheck,
    SafetyProof,
    TransportProposal,
    canonical_hash,
)


@dataclass(frozen=True, slots=True)
class SafetyPolicy:
    version: str = "safety-v1"
    minimum_battery_reserve_percent: float = 20.0
    minimum_obstacle_confidence: float = 0.5
    forbidden_zones: frozenset[str] = frozenset({"forbidden", "human-only"})


class SafetyEngine:
    def __init__(self, policy: SafetyPolicy | None = None) -> None:
        self.policy = policy or SafetyPolicy()

    def verify(
        self,
        *,
        intent: MissionIntent,
        plan: RoutePlan,
        snapshot: OperationalSnapshot,
        proposal: TransportProposal,
    ) -> SafetyProof:
        agvs = {agv.id: agv for agv in snapshot.agvs}
        locations = {location.id: location for location in snapshot.locations}
        pallets = {pallet.id: pallet for pallet in snapshot.pallets}
        nodes = {node.id: node for node in snapshot.nodes}
        selected_agv = agvs.get(plan.selected_agv)

        entities_valid = (
            intent.pallet_id in pallets
            and intent.source in locations
            and intent.destination in locations
            and selected_agv is not None
            and pallets.get(intent.pallet_id) is not None
            and pallets[intent.pallet_id].location_id == intent.source
        )
        map_consistent = (
            plan.map_version == snapshot.map_version
            and proposal.map_version == snapshot.map_version
            and proposal.snapshot_id == snapshot.snapshot_id
        )
        battery_ok = self._battery_ok(selected_agv, plan)
        forbidden_hits = [
            node_id
            for node_id in plan.nodes
            if node_id not in nodes or nodes[node_id].zone in self.policy.forbidden_zones
        ]
        active_obstacles = {
            obstacle.node_id
            for obstacle in snapshot.obstacles
            if obstacle.confidence >= self.policy.minimum_obstacle_confidence
        }
        collision_hits = [node_id for node_id in plan.nodes if node_id in active_obstacles]
        conflicts = [
            group
            for group in plan.reservation_groups
            if group in snapshot.reserved_groups
            and snapshot.reserved_groups[group] != plan.selected_agv
        ]
        destination = locations.get(intent.destination)
        destination_ok = destination is not None and destination.occupancy in {
            None,
            intent.pallet_id,
        }
        proposal_consistent = (
            proposal.mission_goal == intent
            and proposal.selected_agv == plan.selected_agv
            and proposal.route == plan.nodes
            and proposal.route_version == plan.route_version
        )

        checks = [
            self._check("entity_validity", entities_valid, "live entities and pallet source"),
            self._check("map_consistency", map_consistent, "snapshot/map/proposal versions"),
            self._check("battery_reserve", battery_ok, "post-mission reserve >= 20%"),
            self._check("forbidden_zone", not forbidden_hits, f"hits={forbidden_hits}"),
            self._check("collision", not collision_hits, f"hits={collision_hits}"),
            self._check("deadlock", not conflicts, f"reservation_conflicts={conflicts}"),
            self._check("destination_occupancy", destination_ok, "destination can receive pallet"),
            self._check(
                "proposal_semantics",
                proposal_consistent,
                "proposal matches deterministic plan and live intent",
            ),
        ]
        return SafetyProof.issue(
            proposal_id=proposal.proposal_id,
            route_version=plan.route_version,
            snapshot_id=snapshot.snapshot_id,
            checks=checks,
        )

    def verify_replan(
        self,
        *,
        intent: MissionIntent,
        plan: RoutePlan,
        snapshot: OperationalSnapshot,
        original_proposal: TransportProposal,
    ) -> SafetyProof:
        transient = TransportProposal.issue(
            proposal_id=original_proposal.proposal_id,
            intent=intent,
            plan=plan,
            snapshot_id=snapshot.snapshot_id,
            evidence_refs=original_proposal.evidence_refs,
        )
        return self.verify(
            intent=intent,
            plan=plan,
            snapshot=snapshot,
            proposal=transient,
        )

    def _battery_ok(self, agv: AgvState | None, plan: RoutePlan) -> bool:
        return (
            agv is not None
            and agv.battery_percent - plan.estimated_energy_percent
            >= self.policy.minimum_battery_reserve_percent
        )

    @staticmethod
    def _check(name: str, passed: bool, detail: str) -> SafetyCheck:
        evidence = {"name": name, "passed": passed, "detail": detail}
        return SafetyCheck(
            name=name,
            passed=passed,
            detail=detail,
            evidence_hash=canonical_hash(evidence),
        )
