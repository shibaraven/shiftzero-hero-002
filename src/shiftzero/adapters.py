from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from shiftzero.domain import Mission, MissionStatus, RoutePlan, utc_now
from shiftzero.simulator import ReferenceWorld


class ExecutionAdapter(Protocol):
    def start(self, mission: Mission) -> Mission: ...

    def advance(self, mission_id: str) -> Mission: ...

    def local_stop(self, mission_id: str, source: str) -> float: ...

    def replace_route(self, mission_id: str, plan: RoutePlan) -> Mission: ...


class SimulatorAdapter:
    """Idempotent structured execution; never accepts free text."""

    def __init__(self, world: ReferenceWorld) -> None:
        self.world = world
        self._missions: dict[str, Mission] = {}
        self._idempotency_index: dict[str, str] = {}

    @property
    def mission_count(self) -> int:
        return len(self._missions)

    def start(self, mission: Mission) -> Mission:
        previous_id = self._idempotency_index.get(mission.idempotency_key)
        if previous_id:
            return self._missions[previous_id].model_copy(deep=True)
        if mission.status != MissionStatus.APPROVED:
            raise RuntimeError("adapter accepts APPROVED structured missions only")
        stored = mission.model_copy(
            update={"status": MissionStatus.EXECUTING, "updated_at": utc_now()}, deep=True
        )
        self._missions[stored.mission_id] = stored
        self._idempotency_index[stored.idempotency_key] = stored.mission_id
        agv = self.world.agvs[stored.selected_agv]
        agv.state = "EXECUTING"
        agv.current_mission_id = stored.mission_id
        return stored.model_copy(deep=True)

    def advance(self, mission_id: str) -> Mission:
        mission = self._missions[mission_id]
        if mission.status != MissionStatus.EXECUTING:
            raise RuntimeError("only an executing mission can advance")
        next_index = min(mission.current_node_index + 1, len(mission.route) - 1)
        mission.current_node_index = next_index
        mission.updated_at = utc_now()
        self.world.agvs[mission.selected_agv].node_id = mission.route[next_index]
        if next_index == len(mission.route) - 1:
            mission.status = MissionStatus.COMPLETED
            agv = self.world.agvs[mission.selected_agv]
            agv.state = "IDLE"
            agv.current_mission_id = None
            source = self.world.locations[mission.source]
            destination = self.world.locations[mission.destination]
            source.occupancy = None
            source.pallet_id = None
            destination.occupancy = mission.pallet_id
            destination.pallet_id = mission.pallet_id
            self.world.pallets[mission.pallet_id].location_id = mission.destination
        return mission.model_copy(deep=True)

    def local_stop(self, mission_id: str, source: str) -> float:
        if not source:
            raise ValueError("a stop trigger source is required")
        started = time.perf_counter_ns()
        mission = self._missions[mission_id]
        mission.status = MissionStatus.SAFE_STOP
        mission.updated_at = utc_now()
        self.world.agvs[mission.selected_agv].state = "STOPPED"
        completed = time.perf_counter_ns()
        return (completed - started) / 1_000_000

    def replace_route(self, mission_id: str, plan: RoutePlan) -> Mission:
        mission = self._missions[mission_id]
        if mission.status != MissionStatus.SAFE_STOP:
            raise RuntimeError("route replacement requires SAFE_STOP")
        mission.route = plan.nodes
        mission.route_version = plan.route_version
        mission.current_node_index = 0
        mission.status = MissionStatus.EXECUTING
        mission.updated_at = utc_now()
        agv = self.world.agvs[mission.selected_agv]
        agv.state = "EXECUTING"
        return mission.model_copy(deep=True)

    def get(self, mission_id: str) -> Mission:
        return self._missions[mission_id].model_copy(deep=True)


class CompatibilityAttestation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    model: str
    generated_at: str
    official_gate_passed: bool
    report_hash: str

    @classmethod
    def load(cls, path: Path) -> CompatibilityAttestation:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            provider=payload["provider"],
            model=payload["model"],
            generated_at=payload["generated_at"],
            official_gate_passed=payload["official_gate_passed"],
            report_hash=payload["report_hash"],
        )


@dataclass(slots=True)
class RealAgvAdapter:
    """Fail-closed hardware boundary. Vendor transport is intentionally not embedded."""

    attestation: CompatibilityAttestation

    def __post_init__(self) -> None:
        if not self.attestation.official_gate_passed:
            raise RuntimeError("real AGV integration is blocked until the official gate passes")

    def start(self, mission: Mission) -> Mission:
        raise NotImplementedError(
            "bind this boundary to the site-approved VDA5050/MQTT gateway after safety review"
        )

    def local_stop(self, mission_id: str, source: str) -> float:
        raise NotImplementedError(
            "local stop must be implemented on the edge/PLC path, not through this cloud adapter"
        )
