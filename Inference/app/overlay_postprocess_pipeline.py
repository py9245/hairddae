from __future__ import annotations

from typing import Any

import numpy as np


def apply_overlay_postprocess(
    output_frame_bgr: np.ndarray,
    base_frame_bgr: np.ndarray,
    user_row: dict[str, Any],
    *,
    renderer_name: str,
    coverage_mask: np.ndarray | None = None,
) -> np.ndarray:
    _ = (base_frame_bgr, user_row, renderer_name, coverage_mask)
    return output_frame_bgr
