from __future__ import annotations

import json
from pathlib import Path

from shiftzero.domain import (
    ApprovalToken,
    Mission,
    MissionIntent,
    OperationalSnapshot,
    RoutePlan,
    SafetyProof,
    TransportProposal,
)

SCHEMAS = {
    "mission-intent.schema.json": MissionIntent,
    "operational-snapshot.schema.json": OperationalSnapshot,
    "route-plan.schema.json": RoutePlan,
    "transport-proposal.schema.json": TransportProposal,
    "safety-proof.schema.json": SafetyProof,
    "approval-token.schema.json": ApprovalToken,
    "mission.schema.json": Mission,
}


def export_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, model in SCHEMAS.items():
        path = output_dir / filename
        path.write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    from shiftzero.api import app

    openapi_path = output_dir / "openapi.json"
    openapi_path.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(openapi_path)
    return written
