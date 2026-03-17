from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image

from app.catalog import AssetBundle


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


def compose_bundle_frame(frame_image: Image.Image, bundle: AssetBundle | None) -> Image.Image:
    if (
        bundle is None
        or bundle.hair_rgba_path is None
        or bundle.render_task is None
        or bundle.hair_bbox is None
    ):
        return frame_image

    render_task = bundle.render_task
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
        resample=Image.BICUBIC,
    )

    output = frame_image.convert("RGBA")
    roi = output.crop(
        (
            int(destination_roi["x"]),
            int(destination_roi["y"]),
            int(destination_roi["x"]) + roi_width,
            int(destination_roi["y"]) + roi_height,
        ),
    )
    composited_roi = Image.alpha_composite(roi, warped_patch)
    output.paste(
        composited_roi,
        (
            int(destination_roi["x"]),
            int(destination_roi["y"]),
        ),
    )
    return output
