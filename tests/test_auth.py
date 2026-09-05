import pytest

from shiftzero.auth import (
    AuthenticationError,
    AuthSettings,
    issue_access_token,
    verify_access_token,
)


def test_signed_identity_round_trip_and_tamper_rejection() -> None:
    settings = AuthSettings(secret=b"a-secret-that-is-longer-than-thirty-two-bytes")
    token = issue_access_token(subject="alice", role="approver", settings=settings)
    principal = verify_access_token(token, settings)
    assert principal.subject == "alice"
    assert principal.role == "approver"

    with pytest.raises(AuthenticationError, match="signature"):
        verify_access_token(token + "tampered", settings)


def test_auth_configuration_fails_closed_without_strong_secret(monkeypatch) -> None:
    monkeypatch.delenv("SHIFTZERO_AUTH_SECRET", raising=False)
    with pytest.raises(AuthenticationError, match="fails closed"):
        AuthSettings.from_environment()
