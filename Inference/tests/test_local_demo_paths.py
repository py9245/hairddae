from __future__ import annotations

from pathlib import Path
import sys

TOOLS_DIR = Path(__file__).resolve().parents[1] / "hairddae_tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from local_demo_paths import inference_root, repo_root, static_root


def test_local_demo_paths_resolve_repo_roots() -> None:
    assert inference_root() == Path(__file__).resolve().parents[1]
    assert repo_root() == Path(__file__).resolve().parents[2]
    assert static_root() == repo_root() / "static"
