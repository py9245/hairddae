from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def inference_root() -> Path:
    return Path(__file__).resolve().parents[1]


def static_root() -> Path:
    return repo_root() / "static"


def generated_root() -> Path:
    return static_root() / "generated"


def runtime_demo_root() -> Path:
    return static_root() / "runtime_demo"


def cache_root() -> Path:
    return static_root() / "cache"


def ensure_runtime_dirs() -> None:
    for path in [
        generated_root(),
        runtime_demo_root(),
        cache_root(),
        generated_root() / "base_pose_bank",
        generated_root() / "asset_factory_v0",
        generated_root() / "runtime_outputs",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def _resolve_first_existing(candidates: list[Path], label: str) -> Path:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Could not find {label}. Checked: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def _resolve_first_existing_dir(candidates: list[Path], label: str) -> Path:
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        f"Could not find {label}. Checked: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def default_face_landmarker_model_path() -> Path:
    env_value = os.environ.get("FACE_LANDMARKER_TASK")
    candidates = []
    if env_value:
        candidates.append(Path(env_value).expanduser())
    candidates.extend(
        [
            inference_root() / "models" / "face_landmarker.task",
            inference_root() / "third_party" / "models" / "face_landmarker.task",
            static_root() / "third_party" / "models" / "face_landmarker.task",
            Path("/home/yusin/AI_PlanB/m101_poc/public/models/face_landmarker.task"),
        ]
    )
    return _resolve_first_existing(candidates, "MediaPipe face_landmarker.task")


def default_face_parsing_repo_dir() -> Path:
    env_value = os.environ.get("FACE_PARSING_REPO_DIR")
    candidates = []
    if env_value:
        candidates.append(Path(env_value).expanduser())
    candidates.extend(
        [
            inference_root() / "third_party" / "third_party" / "face-parsing.PyTorch",
            inference_root() / "third_party" / "face-parsing.PyTorch",
            static_root() / "third_party" / "third_party" / "face-parsing.PyTorch",
            static_root() / "third_party" / "face-parsing.PyTorch",
        ]
    )
    return _resolve_first_existing_dir(candidates, "face-parsing.PyTorch repo")


def default_face_parsing_weights() -> Path:
    env_value = os.environ.get("FACE_PARSING_WEIGHTS")
    candidates = []
    if env_value:
        candidates.append(Path(env_value).expanduser())
    repo_dir = default_face_parsing_repo_dir()
    candidates.extend(
        [
            repo_dir / "res" / "cp" / "79999_iter.pth",
        ]
    )
    return _resolve_first_existing(candidates, "BiSeNet weights")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def resolve_asset_path(asset_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else asset_root / path


def manifest_json_path(asset_root: Path) -> Path:
    candidates = [
        asset_root / "manifests" / "manifest.json",
        asset_root / "indices" / "asset_manifest.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return asset_root / "manifests" / "manifest.json"


def manifest_jsonl_path(asset_root: Path) -> Path:
    candidates = [
        asset_root / "manifests" / "manifest.jsonl",
        asset_root / "indices" / "manifest.jsonl",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return asset_root / "manifests" / "manifest.jsonl"


def load_manifest_payload(asset_root: Path) -> dict[str, Any]:
    return read_json(manifest_json_path(asset_root))


def load_manifest_items(asset_root: Path) -> list[dict[str, Any]]:
    payload = load_manifest_payload(asset_root)
    return payload.get("items", [])


def write_manifest_outputs(asset_root: Path, payload: dict[str, Any]) -> None:
    manifests_dir = asset_root / "manifests"
    indices_dir = asset_root / "indices"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    indices_dir.mkdir(parents=True, exist_ok=True)

    write_json(manifests_dir / "manifest.json", payload)
    write_json(indices_dir / "asset_manifest.json", payload)

    jsonl_lines = "\n".join(json.dumps(item, ensure_ascii=True) for item in payload.get("items", []))
    for output_path in [manifests_dir / "manifest.jsonl", indices_dir / "manifest.jsonl"]:
        output_path.write_text(jsonl_lines + ("\n" if jsonl_lines else ""), encoding="utf-8")
