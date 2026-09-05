from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenFactorySettings:
    api_key: str
    base_url: str = "https://api.tokenfactory.us-central1.nebius.com/v1/"
    model: str = "nvidia/nemotron-3-super-120b-a12b"
    timeout_seconds: float = 30.0
    max_retries: int = 2
    max_total_inference_seconds: float = 45.0
    circuit_breaker_threshold: int = 3
    circuit_breaker_cooldown_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> TokenFactorySettings:
        api_key = os.getenv("NEBIUS_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "NEBIUS_API_KEY is required for real Token Factory execution; "
                "fixture fallback is intentionally disabled."
            )
        return cls(
            api_key=api_key,
            base_url=os.getenv(
                "NEBIUS_BASE_URL",
                "https://api.tokenfactory.us-central1.nebius.com/v1/",
            ).rstrip("/")
            + "/",
            model=os.getenv("NEBIUS_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
            timeout_seconds=float(os.getenv("NEBIUS_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("NEBIUS_MAX_RETRIES", "2")),
            max_total_inference_seconds=float(
                os.getenv("NEBIUS_MAX_TOTAL_INFERENCE_SECONDS", "45")
            ),
            circuit_breaker_threshold=int(
                os.getenv("NEBIUS_CIRCUIT_BREAKER_THRESHOLD", "3")
            ),
            circuit_breaker_cooldown_seconds=float(
                os.getenv("NEBIUS_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "30")
            ),
        )
