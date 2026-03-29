from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any

import jwt
from jwt import InvalidTokenError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth import InMemoryReplayStore, _unverified_ticket_summary, validate_connect_ticket
from app.config import Settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a connect ticket against the current inference runtime settings.",
    )
    parser.add_argument(
        "--token",
        help="Raw connect ticket JWT. If omitted, INFERENCE_CONNECT_TICKET is used.",
    )
    parser.add_argument(
        "--token-file",
        help="Path to a file containing the raw connect ticket JWT.",
    )
    return parser.parse_args()


def _read_token(args: argparse.Namespace) -> str:
    if args.token:
        return str(args.token).strip()
    if args.token_file:
        with open(args.token_file, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    env_token = os.environ.get("INFERENCE_CONNECT_TICKET", "").strip()
    if env_token:
        return env_token
    raise SystemExit("connect ticket is required: use --token, --token-file, or INFERENCE_CONNECT_TICKET")


def _settings_summary(settings: Settings) -> dict[str, Any]:
    return {
        "node_id": settings.node_id,
        "jwt_issuer": settings.jwt_issuer,
        "ticket_algorithms": list(settings.ticket_algorithms),
        "ticket_audience": settings.ticket_audience,
        "feature_schema_version": settings.feature_schema_version,
        "transform_version": settings.transform_version,
        "rtc_control_channel_name": settings.rtc_control_channel_name,
        "rtc_input": {
            "width": settings.rtc_input_width,
            "height": settings.rtc_input_height,
            "fps": settings.rtc_input_fps,
        },
        "rtc_output": {
            "width": settings.rtc_output_width,
            "height": settings.rtc_output_height,
            "fps": settings.rtc_output_fps,
            "mirrored": settings.rtc_output_mirrored,
        },
    }


async def _main() -> int:
    args = _parse_args()
    settings = Settings.from_env()
    raw_ticket = _read_token(args)

    print(
        json.dumps(
            {
                "runtime_settings": _settings_summary(settings),
                "unverified_claims": _unverified_ticket_summary(raw_ticket),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    try:
        jwt.decode(
            raw_ticket,
            settings.jwt_secret,
            algorithms=list(settings.ticket_algorithms),
            issuer=settings.jwt_issuer,
            audience=settings.ticket_audience,
            options={"require": ["sub", "jti", "exp", "iss", "aud"]},
        )
        print("jwt_decode=ok")
    except InvalidTokenError as exc:
        print(f"jwt_decode=failed reason={exc}")
        return 1

    try:
        claims = await validate_connect_ticket(
            raw_ticket,
            settings,
            InMemoryReplayStore(),
        )
    except Exception as exc:
        print(f"validate_connect_ticket=failed reason={exc}")
        return 1

    print(
        json.dumps(
            {
                "validate_connect_ticket": "ok",
                "claims": {
                    "user_id": claims.user_id,
                    "apply_session_id": claims.apply_session_id,
                    "device_id": claims.device_id,
                    "hair_id": claims.hair_id,
                    "node_id": claims.node_id,
                    "schema_version": claims.schema_version,
                    "dataset_code": claims.dataset_code,
                    "representative_asset_id": claims.representative_asset_id,
                    "token_id": claims.token_id,
                    "expires_at": claims.expires_at.isoformat(),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
