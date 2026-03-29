from __future__ import annotations

import asyncio
import time
import uuid

import jwt

from app.auth import InMemoryReplayStore, TicketValidationError, validate_connect_ticket
from app.config import Settings
from conftest import apply_test_env


def build_settings(monkeypatch) -> Settings:
    apply_test_env(
        monkeypatch,
        INFERENCE_TICKET_ALGORITHMS="HS256,HS384",
        INFERENCE_TICKET_AUDIENCE="inference",
        INFERENCE_NODE_ID="infer-gpu-01",
        INFERENCE_FEATURE_SCHEMA_VERSION="2",
    )
    return Settings.from_env()


def build_token(settings: Settings, algorithm: str = "HS256", **overrides: object) -> str:
    payload: dict[str, object] = {
        "sub": "auth-test-user",
        "jti": str(uuid.uuid4()),
        "exp": int(time.time()) + 300,
        "iss": settings.jwt_issuer,
        "aud": settings.ticket_audience,
        "tokenType": "INFERENCE_CONNECT",
        "single_use": True,
        "node": settings.node_id,
        "sid": "auth-test-session",
        "did": "auth-test-device",
        "hid": 1,
        "ver": settings.feature_schema_version,
        "dataset_code": "0001",
    }
    payload.update(overrides)
    return jwt.encode(payload, settings.jwt_secret, algorithm=algorithm)


def test_validate_connect_ticket_accepts_matching_token(monkeypatch) -> None:
    settings = build_settings(monkeypatch)
    replay_store = InMemoryReplayStore()
    token = build_token(settings)

    claims = asyncio.run(validate_connect_ticket(token, settings, replay_store))

    assert claims.user_id == "auth-test-user"
    assert claims.apply_session_id == "auth-test-session"
    assert claims.device_id == "auth-test-device"
    assert claims.hair_id == 1
    assert claims.node_id == "infer-gpu-01"
    assert claims.schema_version == 2
    assert claims.dataset_code == "0001"


def test_validate_connect_ticket_rejects_replay(monkeypatch) -> None:
    settings = build_settings(monkeypatch)
    replay_store = InMemoryReplayStore()
    token = build_token(settings, jti="replay-test-token")

    asyncio.run(validate_connect_ticket(token, settings, replay_store))

    try:
        asyncio.run(validate_connect_ticket(token, settings, replay_store))
    except TicketValidationError as exc:
        assert str(exc) == "ticket replay detected"
    else:
        raise AssertionError("expected replay detection")


def test_validate_connect_ticket_accepts_matching_hs384_token(monkeypatch) -> None:
    settings = build_settings(monkeypatch)
    replay_store = InMemoryReplayStore()
    token = build_token(settings, algorithm="HS384")

    claims = asyncio.run(validate_connect_ticket(token, settings, replay_store))

    assert claims.user_id == "auth-test-user"
    assert claims.schema_version == 2
