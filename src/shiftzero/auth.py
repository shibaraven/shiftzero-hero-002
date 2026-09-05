from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["operator", "approver", "executor", "safety", "viewer", "admin"]


class AuthenticationError(RuntimeError):
    pass


class Principal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=128)
    role: Role
    issued_at: int
    expires_at: int


@dataclass(frozen=True, slots=True)
class AuthSettings:
    secret: bytes
    issuer: str = "shiftzero-hero002"

    @classmethod
    def from_environment(cls) -> AuthSettings:
        value = os.getenv("SHIFTZERO_AUTH_SECRET", "")
        if len(value) < 32:
            raise AuthenticationError(
                "SHIFTZERO_AUTH_SECRET must contain at least 32 characters; "
                "authentication fails closed"
            )
        return cls(secret=value.encode("utf-8"))


def issue_access_token(
    *, subject: str, role: Role, settings: AuthSettings, ttl_seconds: int = 900
) -> str:
    if ttl_seconds < 1 or ttl_seconds > 86_400:
        raise ValueError("ttl_seconds must be between 1 and 86400")
    now = int(time.time())
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + ttl_seconds,
        "iss": settings.issuer,
    }
    encoded = _b64url(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    signature = _b64url(hmac.new(settings.secret, encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def verify_access_token(token: str, settings: AuthSettings) -> Principal:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = _b64url(
            hmac.new(settings.secret, encoded.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise AuthenticationError("invalid bearer token signature")
        payload = json.loads(_b64url_decode(encoded))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthenticationError("malformed bearer token") from exc
    if payload.get("iss") != settings.issuer:
        raise AuthenticationError("bearer token issuer mismatch")
    now = int(time.time())
    if not isinstance(payload.get("exp"), int) or payload["exp"] <= now:
        raise AuthenticationError("bearer token expired")
    if not isinstance(payload.get("iat"), int) or payload["iat"] > now + 30:
        raise AuthenticationError("bearer token issued_at is invalid")
    try:
        return Principal(
            subject=payload["sub"],
            role=payload["role"],
            issued_at=payload["iat"],
            expires_at=payload["exp"],
        )
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("bearer token claims are invalid") from exc


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding).decode("utf-8")
