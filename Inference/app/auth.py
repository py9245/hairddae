from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import jwt
from jwt import InvalidTokenError
from redis.asyncio import Redis

from app.config import Settings


class TicketValidationError(Exception):
    """Raised when an inference connect ticket is invalid."""


@dataclass(frozen=True)
class TicketClaims:
    user_id: str
    apply_session_id: str
    device_id: str
    hair_id: int
    node_id: str
    schema_version: int
    dataset_code: str
    representative_asset_id: str | None
    token_id: str
    expires_at: datetime


class ReplayStore:
    async def consume(self, token_id: str, ttl_seconds: int) -> bool:
        raise NotImplementedError

    async def close(self) -> None:
        return None


class InMemoryReplayStore(ReplayStore):
    def __init__(self) -> None:
        self._seen: set[str] = set()

    async def consume(self, token_id: str, ttl_seconds: int) -> bool:
        if token_id in self._seen:
            return False
        self._seen.add(token_id)
        return True


class RedisReplayStore(ReplayStore):
    def __init__(self, redis_url: str) -> None:
        self._redis = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)

    async def consume(self, token_id: str, ttl_seconds: int) -> bool:
        key = f"inference:ticket:{token_id}"
        return bool(await self._redis.set(key, "1", ex=max(ttl_seconds, 1), nx=True))

    async def close(self) -> None:
        await self._redis.aclose()


def build_replay_store(settings: Settings) -> ReplayStore:
    if settings.redis_url:
        return RedisReplayStore(settings.redis_url)
    return InMemoryReplayStore()


def _parse_expiration(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    raise TicketValidationError("ticket expiration is missing")


async def validate_connect_ticket(
    raw_ticket: str,
    settings: Settings,
    replay_store: ReplayStore,
) -> TicketClaims:
    try:
        payload = jwt.decode(
            raw_ticket,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.ticket_audience,
            options={
                "require": ["sub", "jti", "exp", "iss", "aud"],
            },
        )
    except InvalidTokenError as exc:
        raise TicketValidationError("invalid connect ticket") from exc

    if payload.get("tokenType") != "INFERENCE_CONNECT":
        raise TicketValidationError("invalid token type")
    if payload.get("single_use") is not True:
        raise TicketValidationError("single_use claim is required")

    node_id = str(payload.get("node", ""))
    if node_id != settings.node_id:
        raise TicketValidationError("ticket node mismatch")

    try:
        claims = TicketClaims(
            user_id=str(payload["sub"]),
            apply_session_id=str(payload["sid"]),
            device_id=str(payload["did"]),
            hair_id=int(payload["hid"]),
            node_id=node_id,
            schema_version=int(payload["ver"]),
            dataset_code=str(payload["dataset_code"]),
            representative_asset_id=(
                None
                if payload.get("representative_asset_id") in (None, "")
                else str(payload["representative_asset_id"])
            ),
            token_id=str(payload["jti"]),
            expires_at=_parse_expiration(payload["exp"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TicketValidationError("ticket claims are incomplete") from exc

    if claims.schema_version != settings.feature_schema_version:
        raise TicketValidationError("schema version mismatch")

    now = datetime.now(tz=timezone.utc)
    ttl_seconds = int((claims.expires_at - now).total_seconds())
    if ttl_seconds <= 0:
        raise TicketValidationError("ticket expired")

    consumed = await replay_store.consume(claims.token_id, ttl_seconds)
    if not consumed:
        raise TicketValidationError("ticket replay detected")

    return claims
