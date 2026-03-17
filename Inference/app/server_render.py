from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image

from app.catalog import AssetBundle


RESAMPLE_FILTER = Image.Resampling.BILINEAR


@lru_cache(maxsize=64)
def _load_rgba_image(path: str) -> Image.Image:
    return Image.open(path).convert("RGBA")


def _invert_affine(a: float, b: float, c: float, d: float, e: float, f: float) -> tuple[float, ...] | None:
    determinant = a * d - b * c
    if abs(determinant) < 1e-8:
        return None

    inv_a = d / determinant
    inv_b = -b / determinant
    inv_c = -c / determinant
    inv_d = a / determinant
    inv_e = (c * f - d * e) / determinant
    inv_f = (b * e - a * f) / determinant
    return (inv_a, inv_c, inv_e, inv_b, inv_d, inv_f)


def _scale_render_task(
    render_task: dict[str, object],
    reference_width: int,
    reference_height: int,
    frame_width: int,
    frame_height: int,
) -> dict[str, object]:
    if (
        reference_width <= 0
        or reference_height <= 0
        or frame_width <= 0
        or frame_height <= 0
        or (reference_width == frame_width and reference_height == frame_height)
    ):
        return render_task

    matrix = render_task.get("matrix")
    destination_roi = render_task.get("destination_roi")
    destination_quad = render_task.get("destination_quad")
    if not isinstance(matrix, dict) or not isinstance(destination_roi, dict):
        return render_task

    scale_x = frame_width / reference_width
    scale_y = frame_height / reference_height

    scaled_task = dict(render_task)
    scaled_task["matrix"] = {
        "a": float(matrix["a"]) * scale_x,
        "b": float(matrix["b"]) * scale_y,
        "c": float(matrix["c"]) * scale_x,
        "d": float(matrix["d"]) * scale_y,
        "e": float(matrix["e"]) * scale_x,
        "f": float(matrix["f"]) * scale_y,
    }
    scaled_task["destination_roi"] = {
        "x": int(round(float(destination_roi["x"]) * scale_x)),
        "y": int(round(float(destination_roi["y"]) * scale_y)),
        "w": int(round(float(destination_roi["w"]) * scale_x)),
        "h": int(round(float(destination_roi["h"]) * scale_y)),
    }
    if isinstance(destination_quad, list):
        scaled_task["destination_quad"] = [
            {
                "x": round(float(point["x"]) * scale_x, 3),
                "y": round(float(point["y"]) * scale_y, 3),
            }
            for point in destination_quad
            if isinstance(point, dict)
        ]
    return scaled_task


def compose_bundle_frame(
    frame_image: Image.Image,
    bundle: AssetBundle | None,
    *,
    reference_width: int | None = None,
    reference_height: int | None = None,
) -> Image.Image:
    if (
        bundle is None
        or bundle.hair_rgba_path is None
        or bundle.render_task is None
        or bundle.hair_bbox is None
    ):
        return frame_image

    render_task = bundle.render_task
    if reference_width is not None and reference_height is not None:
        render_task = _scale_render_task(
            render_task,
            reference_width=reference_width,
            reference_height=reference_height,
            frame_width=frame_image.width,
            frame_height=frame_image.height,
        )
    destination_roi = render_task.get("destination_roi")
    matrix = render_task.get("matrix")
    if not destination_roi or not matrix:
        return frame_image

    roi_width = int(destination_roi["w"])
    roi_height = int(destination_roi["h"])
    if roi_width <= 0 or roi_height <= 0:
        return frame_image

    bundle_image = _load_rgba_image(str(bundle.hair_rgba_path))
    source_patch = bundle_image
    source_origin_x = int(bundle.hair_bbox["x"])
    source_origin_y = int(bundle.hair_bbox["y"])

    local_e = (
        float(matrix["a"]) * float(source_origin_x)
        + float(matrix["c"]) * float(source_origin_y)
        + float(matrix["e"])
        - float(destination_roi["x"])
    )
    local_f = (
        float(matrix["b"]) * float(source_origin_x)
        + float(matrix["d"]) * float(source_origin_y)
        + float(matrix["f"])
        - float(destination_roi["y"])
    )

    inverse = _invert_affine(
        float(matrix["a"]),
        float(matrix["b"]),
        float(matrix["c"]),
        float(matrix["d"]),
        local_e,
        local_f,
    )
    if inverse is None:
        return frame_image

    warped_patch = source_patch.transform(
        (roi_width, roi_height),
        Image.AFFINE,
        inverse,
        resample=RESAMPLE_FILTER,
    )

    output = frame_image if frame_image.mode == "RGB" else frame_image.convert("RGB")
    box = (
        int(destination_roi["x"]),
        int(destination_roi["y"]),
        int(destination_roi["x"]) + roi_width,
        int(destination_roi["y"]) + roi_height,
    )
    base_roi = output.crop(box).convert("RGBA")
    composited_roi = Image.alpha_composite(base_roi, warped_patch)
    output.paste(composited_roi.convert(output.mode), box[:2])
    return output
