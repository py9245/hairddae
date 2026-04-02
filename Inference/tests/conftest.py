from __future__ import annotations

import os
from pathlib import Path

import pytest

TEST_JWT_SECRET = "hairddae-test-secret-key-2026-inference"
TEST_JWT_ISSUER = "hairddae-test"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def inference_root() -> Path:
    return Path(__file__).resolve().parents[1]


def face_landmarker_model_path() -> Path:
    return inference_root() / "models" / "face_landmarker.task"


def static_root() -> Path:
    return repo_root() / "static"


def apply_test_env(
    monkeypatch: pytest.MonkeyPatch | None = None,
    **extra_env: str,
) -> None:
    env = {
        "INFERENCE_JWT_SECRET": TEST_JWT_SECRET,
        "INFERENCE_JWT_ISSUER": TEST_JWT_ISSUER,
        "INFERENCE_STATIC_ROOT": str(static_root()),
        "INFERENCE_STATIC_BASE_URL": "/static",
        "INFERENCE_FACE_LANDMARKER_MODEL_PATH": str(face_landmarker_model_path()),
    }
    env.update(extra_env)

    if monkeypatch is None:
        for name, value in env.items():
            os.environ[name] = value
        os.environ.pop("INFERENCE_REDIS_URL", None)
        return

    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("INFERENCE_REDIS_URL", raising=False)
