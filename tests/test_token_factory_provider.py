import json

import httpx

from shiftzero.agent import TokenFactoryProvider
from shiftzero.config import TokenFactorySettings


def _response(
    arguments: dict, *, status: int = 200, tool_name: str = "parse_mission_intent"
) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"x-request-id": "req-test", "x-ratelimit-remaining-requests": "9"},
        json={
            "id": "chatcmpl-test",
            "model": "nvidia/nemotron-3-super-120b-a12b",
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call-test",
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(arguments),
                                },
                            }
                        ]
                    },
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


def _provider(handler) -> TokenFactoryProvider:
    settings = TokenFactorySettings(api_key="test", max_retries=1)
    client = httpx.Client(
        base_url=settings.base_url,
        transport=httpx.MockTransport(handler),
    )
    return TokenFactoryProvider(settings, client=client)


def test_real_provider_contract_parses_forced_tool_call() -> None:
    provider = _provider(
        lambda request: _response(
            {
                "pallet_id": "P-104",
                "source": "INBOUND-01",
                "destination": "RACK-A12",
                "requested_agv": None,
                "constraints": ["avoid-human-zone"],
            }
        )
    )
    intent, evidence = provider.parse_intent("Move P-104 from INBOUND-01 to RACK-A12")
    assert intent.pallet_id == "P-104"
    assert evidence.provider == "nebius_token_factory"
    assert evidence.request_id == "req-test"
    assert evidence.tool_name == "parse_mission_intent"
    assert len(evidence.tool_arguments_hash) == 64
    assert evidence.tool_result_hash == evidence.tool_arguments_hash
    assert evidence.inference_budget_ms == 45_000


def test_one_schema_repair_is_allowed_without_side_effect() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response({"pallet_id": "invalid"})
        return _response(
            {
                "pallet_id": "P-104",
                "source": "INBOUND-01",
                "destination": "RACK-A12",
                "requested_agv": None,
                "constraints": ["avoid-human-zone"],
            }
        )

    _, evidence = _provider(handler).parse_intent("Move the pallet")
    assert evidence.repair_count == 1
    assert calls == 2


def test_429_retries_with_the_same_idempotency_key() -> None:
    calls = 0
    keys = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        keys.append(request.headers.get("idempotency-key"))
        if calls == 1:
            return httpx.Response(429, request=request, json={"error": "limited"})
        response = _response(
            {
                "pallet_id": "P-104",
                "source": "INBOUND-01",
                "destination": "RACK-A12",
                "requested_agv": None,
                "constraints": ["avoid-human-zone"],
            }
        )
        response.request = request
        return response

    _, evidence = _provider(handler).parse_intent("Move the pallet")
    assert evidence.retry_count == 1
    assert calls == 2
    assert keys[0] == keys[1]


def test_timeout_fails_closed_after_bounded_retry() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("injected timeout", request=request)

    try:
        _provider(handler).parse_intent("Move the pallet")
    except RuntimeError as exc:
        assert "failed closed" in str(exc)
    else:
        raise AssertionError("timeout unexpectedly produced an intent")
    assert calls == 2


def test_circuit_breaker_opens_after_bounded_failure() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("injected timeout", request=request)

    settings = TokenFactorySettings(
        api_key="test",
        max_retries=0,
        circuit_breaker_threshold=1,
        circuit_breaker_cooldown_seconds=30,
    )
    provider = TokenFactoryProvider(
        settings,
        client=httpx.Client(
            base_url=settings.base_url,
            transport=httpx.MockTransport(handler),
        ),
    )
    for expected in ("failed closed", "circuit breaker is open"):
        try:
            provider.parse_intent("Move the pallet")
        except RuntimeError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("provider unexpectedly returned while faulted")
    assert calls == 1
