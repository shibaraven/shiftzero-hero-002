from __future__ import annotations

import heapq
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from shiftzero.domain import (
    AgvState,
    LocationInspection,
    LocationState,
    MapEdge,
    MapNode,
    MissionIntent,
    ObstacleGeometry,
    ObstacleState,
    OperationalSnapshot,
    PalletState,
    Pose,
    RoutePlan,
    RouteReservation,
    canonical_hash,
    utc_now,
)


class ScenarioExpected(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pallet_id: str
    source: str
    destination: str
    selected_agv: str
    incident: str
    outcome: str


class ScenarioMap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    nodes: list[MapNode]
    edges: list[MapEdge]


class BlockageDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    obstacle_id: str
    node_id: str
    confidence: float
    source: str = "reference_simulator"
    ttl_seconds: float = 30
    profile: str = "sudden"


class HeroScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str
    seed: int
    operator_text: str
    expected: ScenarioExpected
    map: ScenarioMap
    agvs: list[AgvState]
    locations: list[LocationState]
    pallets: list[PalletState]
    blockage: BlockageDefinition

    @classmethod
    def load(cls, path: Path) -> HeroScenario:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class NoFeasiblePlan(RuntimeError):
    pass


@dataclass
class ReferenceWorld:
    scenario: HeroScenario

    def __post_init__(self) -> None:
        self.nodes = {node.id: node.model_copy(deep=True) for node in self.scenario.map.nodes}
        self.edges = [edge.model_copy(deep=True) for edge in self.scenario.map.edges]
        self.agvs = {agv.id: agv.model_copy(deep=True) for agv in self.scenario.agvs}
        self.locations = {
            location.id: location.model_copy(deep=True) for location in self.scenario.locations
        }
        self.pallets = {pallet.id: pallet.model_copy(deep=True) for pallet in self.scenario.pallets}
        self.obstacles: dict[str, ObstacleState] = {}
        self.reserved_groups: dict[str, str] = {}
        self.route_reservations: list[RouteReservation] = []
        self.wait_for: dict[str, str] = {}
        self._snapshot_sequence = 0

    def snapshot(self) -> OperationalSnapshot:
        self._snapshot_sequence += 1
        agvs = []
        for agv in self.agvs.values():
            node = self.nodes[agv.node_id]
            agvs.append(
                agv.model_copy(
                    update={"pose": Pose(node_id=node.id, x=node.x, y=node.y)},
                    deep=True,
                )
            )
        return OperationalSnapshot(
            snapshot_id=f"SNAP-{self._snapshot_sequence:04d}",
            captured_at=utc_now(),
            map_version=self.scenario.map.version,
            nodes=list(self.nodes.values()),
            edges=self.edges,
            agvs=agvs,
            locations=list(self.locations.values()),
            pallets=list(self.pallets.values()),
            obstacles=list(self.obstacles.values()),
            reserved_groups=self.reserved_groups,
            route_reservations=self.route_reservations,
            wait_for=self.wait_for,
        )

    def inspect_location(self, location_id: str, snapshot_id: str) -> LocationInspection:
        location = self.locations.get(location_id)
        if location is None:
            return LocationInspection(
                location_id=location_id, exists=False, snapshot_id=snapshot_id
            )
        return LocationInspection(
            location_id=location.id,
            exists=True,
            node_id=location.node_id,
            occupancy=location.occupancy,
            snapshot_id=snapshot_id,
        )

    def add_hero_blockage(self) -> ObstacleState:
        definition = self.scenario.blockage
        obstacle = ObstacleState(
            id=definition.obstacle_id,
            node_id=definition.node_id,
            confidence=definition.confidence,
            source=definition.source,
            ttl_seconds=definition.ttl_seconds,
            observation_count=1,
            geometry=ObstacleGeometry(
                type="Point",
                coordinates=[
                    self.nodes[definition.node_id].x,
                    self.nodes[definition.node_id].y,
                ],
            ),
        )
        self.obstacles[obstacle.id] = obstacle
        return obstacle

    def remove_obstacle(self, obstacle_id: str) -> None:
        self.obstacles.pop(obstacle_id, None)


class DeterministicPlanner:
    energy_percent_per_meter = 0.75

    def plan(
        self,
        *,
        intent: MissionIntent,
        snapshot: OperationalSnapshot,
        start_node: str | None = None,
        force_agv: str | None = None,
    ) -> RoutePlan:
        locations = {location.id: location for location in snapshot.locations}
        source = locations.get(intent.source)
        destination = locations.get(intent.destination)
        if (
            source is None
            or destination is None
            or not source.reachable
            or not destination.reachable
        ):
            raise NoFeasiblePlan("source or destination is absent from the live snapshot")

        agv, candidate_count = self._select_agv(intent, snapshot, force_agv)
        origin = start_node or source.node_id
        blocked_nodes = {
            obstacle.node_id
            for obstacle in snapshot.obstacles
            if obstacle.last_seen.timestamp() + obstacle.ttl_seconds
            >= snapshot.captured_at.timestamp()
            and (obstacle.confidence >= 0.9 or obstacle.observation_count >= 2)
        }
        forbidden_nodes = {
            node.id for node in snapshot.nodes if node.zone in {"forbidden", "human-only"}
        }
        path, edges = self._shortest_path(
            origin,
            destination.node_id,
            snapshot.edges,
            blocked_nodes | forbidden_nodes,
        )
        distance = sum(edge.length_m for edge in edges)
        duration = sum(edge.length_m / edge.speed_limit_mps for edge in edges)
        energy = round(distance * self.energy_percent_per_meter, 3)
        route_content: dict[str, Any] = {
            "map_version": snapshot.map_version,
            "selected_agv": agv.id,
            "nodes": path,
            "reservation_groups": [edge.reservation_group for edge in edges],
            "distance_m": distance,
        }
        return RoutePlan(
            route_version=f"route-{canonical_hash(route_content)[:12]}",
            map_version=snapshot.map_version,
            selected_agv=agv.id,
            nodes=path,
            reservation_groups=route_content["reservation_groups"],
            distance_m=distance,
            estimated_energy_percent=energy,
            cost=round(distance, 3),
            estimated_duration_seconds=round(duration, 3),
            candidate_count=candidate_count,
        )

    def _select_agv(
        self,
        intent: MissionIntent,
        snapshot: OperationalSnapshot,
        force_agv: str | None,
    ) -> tuple[AgvState, int]:
        requested = force_agv or intent.requested_agv
        allowed_states = {"IDLE", "STOPPED"} if force_agv else {"IDLE"}
        candidates = [
            agv
            for agv in snapshot.agvs
            if agv.state in allowed_states and "pallet" in agv.capabilities
        ]
        if requested:
            candidates = [agv for agv in candidates if agv.id == requested]
        if not candidates:
            raise NoFeasiblePlan("no idle pallet-capable AGV is available")
        return sorted(candidates, key=lambda agv: (-agv.battery_percent, agv.id))[0], len(
            candidates
        )

    @staticmethod
    def _shortest_path(
        start: str,
        destination: str,
        edges: list[MapEdge],
        forbidden_nodes: set[str],
    ) -> tuple[list[str], list[MapEdge]]:
        graph: dict[str, list[tuple[str, MapEdge]]] = {}
        for edge in edges:
            graph.setdefault(edge.from_node, []).append((edge.to_node, edge))
            if edge.direction == "bidirectional":
                graph.setdefault(edge.to_node, []).append((edge.from_node, edge))
        queue: list[tuple[float, str, list[str], list[MapEdge]]] = [(0, start, [start], [])]
        best: dict[str, float] = {}
        while queue:
            distance, node, path, path_edges = heapq.heappop(queue)
            if node in best and best[node] <= distance:
                continue
            best[node] = distance
            if node == destination:
                return path, path_edges
            for neighbor, edge in sorted(graph.get(node, []), key=lambda item: item[0]):
                if neighbor in forbidden_nodes or neighbor in path:
                    continue
                heapq.heappush(
                    queue,
                    (distance + edge.length_m, neighbor, [*path, neighbor], [*path_edges, edge]),
                )
        raise NoFeasiblePlan(f"no safe route from {start} to {destination}")


def load_default_scenario() -> HeroScenario:
    root = Path(__file__).resolve().parents[2]
    return HeroScenario.load(root / "scenarios" / "hero.json")


def load_compatibility_manifest() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    return json.loads(
        (root / "scenarios" / "compatibility_manifest.json").read_text(encoding="utf-8")
    )
