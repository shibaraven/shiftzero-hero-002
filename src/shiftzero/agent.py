from __future__ import annotations

import json
import random
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from shiftzero.config import TokenFactorySettings
from shiftzero.domain import (
    MissionIntent,
    ModelCallEvidence,
    OperationalSnapshot,
    RoutePlan,
    TransportProposal,
    canonical_hash,
)


class ProviderError(RuntimeError):
    pass


class IntentProposalProvider(Protocol):
    provider_name: str
    model_name: str

    def parse_intent(self, operator_text: str) -> tuple[MissionIntent, ModelCallEvidence]: ...

    def propose_transport(
        self,
        *,
        intent: MissionIntent,
        snapshot: OperationalSnapshot,
        plan: RoutePlan,
        evidence_refs: list[str],
    ) -> tuple[TransportProposal, ModelCallEvidence]: ...


class FixtureProvider:
    """Deterministic development fixture that cannot be confused with live evidence."""

    provider_name = "fixture"
    model_name = "deterministic-fixture-not-a-model"

    def parse_intent(self, operator_text: str) -> tuple[MissionIntent, ModelCallEvidence]:
        started = datetime.now(UTC)
        pallet = _extract(r"\bP-\d+\b", operator_text, "P-104")
        locations = re.findall(r"\b(?:INBOUND|RACK)-[A-Z]*\d+\b", operator_text.upper())
        source = locations[0] if locations else "INBOUND-01"
        destination = locations[1] if len(locations) > 1 else "RACK-A12"
        agv = _extract(r"\bAGV-\d+\b", operator_text.upper(), None)
        intent = MissionIntent(
            pallet_id=pallet,
            source=source,
            destination=destination,
            requested_agv=agv,
            constraints=["avoid-human-zone"],
        )
        completed = datetime.now(UTC)
        return intent, _fixture_evidence(
            tool_name="parse_mission_intent",
            arguments=intent.model_dump(mode="json"),
            started=started,
            completed=completed,
        )

    def propose_transport(
        self,
        *,
        intent: MissionIntent,
        snapshot: OperationalSnapshot,
        plan: RoutePlan,
        evidence_refs: list[str],
    ) -> tuple[TransportProposal, ModelCallEvidence]:
        started = datetime.now(UTC)
        proposal = TransportProposal.issue(
            proposal_id=f"TP-{uuid.uuid4().hex[:10].upper()}",
            intent=intent,
            plan=plan,
            snapshot_id=snapshot.snapshot_id,
            evidence_refs=evidence_refs,
        )
        completed = datetime.now(UTC)
        return proposal, _fixture_evidence(
            tool_name="propose_transport",
            arguments=proposal.model_dump(mode="json"),
            started=started,
            completed=completed,
        )


class TokenFactoryProvider:
    provider_name = "nebius_token_factory"

    def __init__(
        self,
        settings: TokenFactorySettings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.model_name = settings.model
        self.client = client or httpx.Client(
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def parse_intent(self, operator_text: str) -> tuple[MissionIntent, ModelCallEvidence]:
        schema = MissionIntent.model_json_schema()
        body = {
            "model": self.settings.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract a warehouse mission intent. Do not invent identifiers. "
                        "Call parse_mission_intent exactly once. The deterministic backend "
                        "will validate all entities before any side effect."
                    ),
                },
                {"role": "user", "content": operator_text},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "parse_mission_intent",
                        "description": (
                            "Return the typed warehouse mission requested by the operator."
                        ),
                        "parameters": schema,
                    },
                }
            ],
            "tool_choice": {
                "type": "function",
                "function": {"name": "parse_mission_intent"},
            },
            "temperature": 1.0,
            "top_p": 0.95,
        }
        arguments, evidence = self._call_tool(body, "parse_mission_intent", MissionIntent)
        return MissionIntent.model_validate(arguments), evidence

    def propose_transport(
        self,
        *,
        intent: MissionIntent,
        snapshot: OperationalSnapshot,
        plan: RoutePlan,
        evidence_refs: list[str],
    ) -> tuple[TransportProposal, ModelCallEvidence]:
        tool_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "pallet_id",
                "source",
                "destination",
                "candidate_agv",
                "route_version",
                "evidence_refs",
            ],
            "properties": {
                "pallet_id": {"type": "string"},
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "candidate_agv": {"type": "string"},
                "route_version": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
            },
        }
        verified_context = {
            "intent": intent.model_dump(mode="json"),
            "snapshot_id": snapshot.snapshot_id,
            "map_version": snapshot.map_version,
            "deterministic_plan": plan.model_dump(mode="json"),
            "evidence_refs": evidence_refs,
        }
        body = {
            "model": self.settings.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You may only propose the supplied deterministic warehouse plan. "
                        "Copy identifiers and versions exactly from VERIFIED_CONTEXT. "
                        "Call propose_transport once; never approve or dispatch."
                    ),
                },
                {
                    "role": "user",
                    "content": "VERIFIED_CONTEXT\n" + json.dumps(verified_context, sort_keys=True),
                },
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "propose_transport",
                        "description": (
                            "Create a proposal only; this tool has no execution side effect."
                        ),
                        "parameters": tool_schema,
                    },
                }
            ],
            "tool_choice": {
                "type": "function",
                "function": {"name": "propose_transport"},
            },
            "temperature": 1.0,
            "top_p": 0.95,
        }
        arguments, evidence = self._call_tool(body, "propose_transport", None)
        expected = {
            "pallet_id": intent.pallet_id,
            "source": intent.source,
            "destination": intent.destination,
            "candidate_agv": plan.selected_agv,
            "route_version": plan.route_version,
            "evidence_refs": evidence_refs,
        }
        if arguments != expected:
            raise ProviderError(
                "schema-valid proposal failed referential/semantic validation: "
                f"expected={expected!r}, received={arguments!r}"
            )
        proposal = TransportProposal.issue(
            proposal_id=f"TP-{uuid.uuid4().hex[:10].upper()}",
            intent=intent,
            plan=plan,
            snapshot_id=snapshot.snapshot_id,
            evidence_refs=evidence_refs,
        )
        return proposal, evidence

    def verify_connectivity(self) -> ModelCallEvidence:
        intent, evidence = self.parse_intent(
            "Move pallet P-104 from INBOUND-01 to RACK-A12 while avoiding human-only zones."
        )
        if intent.pallet_id != "P-104" or intent.destination != "RACK-A12":
            raise ProviderError("live model returned semantically incorrect verification intent")
        return evidence

    def _call_tool(
        self,
        body: dict[str, Any],
        expected_tool: str,
        response_model: type[MissionIntent] | None,
    ) -> tuple[dict[str, Any], ModelCallEvidence]:
        retry_count = 0
        repair_count = 0
        idempotency_key = str(uuid.uuid4())
        last_error: Exception | None = None
        while repair_count <= 1:
            started = datetime.now(UTC)
            started_ns = time.perf_counter_ns()
            response: httpx.Response | None = None
            for attempt in range(self.settings.max_retries + 1):
                try:
                    response = self.client.post(
                        "chat/completions",
                        json=body,
                        headers={"Idempotency-Key": idempotency_key},
                    )
                    if response.status_code == 429 or response.status_code >= 500:
                        response.raise_for_status()
                    break
                except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    if attempt >= self.settings.max_retries:
                        raise ProviderError(
                            f"Token Factory request failed closed after {attempt + 1} attempts"
                        ) from exc
                    retry_count += 1
                    time.sleep(min(0.25 * (2**attempt) + random.uniform(0, 0.1), 1.0))
            if response is None:
                raise ProviderError("Token Factory returned no response") from last_error
            response.raise_for_status()
            completed = datetime.now(UTC)
            latency_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            payload = response.json()
            try:
                choice = payload["choices"][0]
                calls = choice["message"]["tool_calls"]
                if len(calls) != 1 or calls[0]["function"]["name"] != expected_tool:
                    raise ValueError("unexpected tool call count or name")
                arguments = json.loads(calls[0]["function"]["arguments"])
                if response_model is not None:
                    response_model.model_validate(arguments)
            except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
                last_error = exc
                if repair_count >= 1:
                    raise ProviderError(
                        "tool output invalid after one side-effect-free repair"
                    ) from exc
                repair_count += 1
                body = {
                    **body,
                    "messages": [
                        *body["messages"],
                        {
                            "role": "system",
                            "content": (
                                f"Your previous output was invalid: {type(exc).__name__}. "
                                f"Call {expected_tool} exactly once with schema-valid arguments."
                            ),
                        },
                    ],
                }
                continue

            usage = payload.get("usage") or {}
            request_id = (
                response.headers.get("x-request-id")
                or payload.get("id")
                or f"missing-{uuid.uuid4().hex[:8]}"
            )
            evidence = ModelCallEvidence(
                provider=self.provider_name,
                model=payload.get("model") or self.settings.model,
                request_id=request_id,
                started_at=started,
                completed_at=completed,
                latency_ms=round(latency_ms, 3),
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                finish_reason=choice.get("finish_reason"),
                tool_name=expected_tool,
                tool_arguments_hash=canonical_hash(arguments),
                retry_count=retry_count,
                repair_count=repair_count,
                http_status=response.status_code,
                rate_limit_remaining=response.headers.get("x-ratelimit-remaining-requests"),
                rate_limit_reset=response.headers.get("x-ratelimit-reset-requests"),
            )
            return arguments, evidence
        raise ProviderError("unreachable tool-call failure")


def _extract(pattern: str, text: str, default: str | None) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(0).upper() if match else default


def _fixture_evidence(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    started: datetime,
    completed: datetime,
) -> ModelCallEvidence:
    return ModelCallEvidence(
        provider="fixture",
        model="deterministic-fixture-not-a-model",
        request_id=f"FIXTURE-{uuid.uuid4().hex[:8].upper()}",
        started_at=started,
        completed_at=completed,
        latency_ms=max((completed - started).total_seconds() * 1000, 0.001),
        tool_name=tool_name,
        tool_arguments_hash=canonical_hash(arguments),
        http_status=None,
    )
