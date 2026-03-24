from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image

from app.catalog import AssetBundle


RESAMPLE_FILTER = Image.Resampling.BILINEAR


def _apply_rgba_rgb_gain(image: Image.Image, rgb_gain: float) -> Image.Image:
    if abs(float(rgb_gain) - 1.0) <= 0.02:
        return image

    rgba = np.asarray(image, dtype=np.uint8)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        return image

    alpha_mask = rgba[:, :, 3] >= 8
    if not np.any(alpha_mask):
        return image

    adjusted = rgba.copy()
    rgb = adjusted[:, :, :3].astype(np.float32)
    rgb[alpha_mask] *= float(rgb_gain)
    adjusted[:, :, :3] = np.clip(rgb, 0.0, 255.0).astype(np.uint8)
    return Image.fromarray(adjusted, mode="RGBA")


@lru_cache(maxsize=64)
def _load_rgba_image(path: str) -> Image.Image:
    return Image.open(path).convert("RGBA")


@lru_cache(maxsize=64)
def _load_mask_image(path: str) -> Image.Image:
    return Image.open(path).convert("L")


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


def _coverage_mask_from_warped_patch(
    warped_patch: Image.Image,
    *,
    feather_px: int | None = None,
    alpha_threshold: int = 24,
) -> np.ndarray | None:
    rgba = np.asarray(warped_patch, dtype=np.uint8)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        return None

    alpha = rgba[:, :, 3]
    if alpha.size == 0 or int(np.max(alpha)) < alpha_threshold:
        return None

    hard_mask = np.where(alpha >= alpha_threshold, np.uint8(255), np.uint8(0))
    if int(np.count_nonzero(hard_mask)) == 0:
        return None

    resolved_feather_px = feather_px
    if resolved_feather_px is None:
        resolved_feather_px = max(2, int(round(min(alpha.shape[:2]) * 0.035)))
    resolved_feather_px = max(0, int(resolved_feather_px))

    if resolved_feather_px > 0:
        kernel_size = max(3, resolved_feather_px * 2 + 1)
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        hard_mask = cv2.dilate(hard_mask, kernel, iterations=1)

    soft_mask = hard_mask.astype(np.float32) / 255.0
    if resolved_feather_px > 0:
        sigma = max(0.85, resolved_feather_px * 0.55)
        soft_mask = cv2.GaussianBlur(soft_mask, (0, 0), sigmaX=sigma, sigmaY=sigma)
    alpha_soft = np.clip(alpha.astype(np.float32) / 255.0, 0.0, 1.0)
    soft_mask = np.maximum(soft_mask, np.clip(alpha_soft * 1.1, 0.0, 1.0))
    return np.clip(soft_mask, 0.0, 1.0)


def _restore_uncovered_base_roi(
    suppressed_roi: Image.Image,
    original_roi: Image.Image,
    warped_patch: Image.Image,
    *,
    feather_px: int | None = None,
    alpha_threshold: int = 24,
) -> Image.Image:
    coverage_mask = _coverage_mask_from_warped_patch(
        warped_patch,
        feather_px=feather_px,
        alpha_threshold=alpha_threshold,
    )
    if coverage_mask is None:
        return original_roi

    suppressed_rgba = np.asarray(suppressed_roi.convert("RGBA"), dtype=np.uint8).astype(np.float32)
    original_rgba = np.asarray(original_roi.convert("RGBA"), dtype=np.uint8).astype(np.float32)
    coverage = coverage_mask[..., None]
    blended_rgba = original_rgba * (1.0 - coverage) + suppressed_rgba * coverage
    blended_rgba[:, :, 3] = 255.0
    return Image.fromarray(np.clip(blended_rgba, 0.0, 255.0).astype(np.uint8), mode="RGBA")


def _replace_asset_skin_with_base_roi(
    warped_patch: Image.Image,
    base_roi: Image.Image,
    *,
    skin_replacement_color_rgb: np.ndarray | None,
    face_mask_path: Path | None,
    protect_face_mask_path: Path | None,
    hair_bbox: dict[str, object] | None,
    inverse: tuple[float, ...],
    roi_width: int,
    roi_height: int,
    debug_payload: dict[str, object] | None = None,
) -> Image.Image:
    if hair_bbox is None:
        return warped_patch
    usable_mask_paths = [
        path
        for path in (face_mask_path, protect_face_mask_path)
        if isinstance(path, Path) and path.is_file()
    ]
    if not usable_mask_paths:
        return warped_patch

    source_x = int(hair_bbox.get("x", 0))
    source_y = int(hair_bbox.get("y", 0))
    source_w = int(hair_bbox.get("w", 0))
    source_h = int(hair_bbox.get("h", 0))
    if source_w <= 0 or source_h <= 0:
        return warped_patch

    combined_face_mask = np.zeros((roi_height, roi_width), dtype=np.uint8)
    mask_load_ms = 0.0
    mask_load_count = 0
    mask_cache_hits = 0
    for mask_path in usable_mask_paths:
        try:
            mask_cache_info_before = _load_mask_image.cache_info()
            mask_load_started_at = time.perf_counter()
            source_mask = _load_mask_image(str(mask_path))
            mask_load_ms += (time.perf_counter() - mask_load_started_at) * 1000.0
            mask_load_count += 1
            if _load_mask_image.cache_info().hits > mask_cache_info_before.hits:
                mask_cache_hits += 1
        except Exception:
            continue
        source_patch = source_mask.crop((source_x, source_y, source_x + source_w, source_y + source_h))
        warped_face = source_patch.transform(
            (roi_width, roi_height),
            Image.AFFINE,
            inverse,
            resample=RESAMPLE_FILTER,
        )
        warped_face_mask = np.asarray(warped_face, dtype=np.uint8)
        if warped_face_mask.ndim != 2:
            continue
        combined_face_mask = np.maximum(combined_face_mask, warped_face_mask)
    if debug_payload is not None:
        debug_payload["mask_load_ms"] = round(mask_load_ms, 3)
        debug_payload["mask_load_count"] = mask_load_count
        debug_payload["mask_cache_hits"] = mask_cache_hits

    face_mask = combined_face_mask
    if int(np.count_nonzero(face_mask >= 16)) == 0:
        return warped_patch
    warped_rgba = np.asarray(warped_patch, dtype=np.uint8)
    base_rgba = np.asarray(base_roi.convert("RGBA"), dtype=np.uint8)
    if warped_rgba.shape != base_rgba.shape or warped_rgba.ndim != 3 or warped_rgba.shape[2] != 4:
        return warped_patch

    rgb = warped_rgba[:, :, :3].astype(np.float32)
    alpha = warped_rgba[:, :, 3]
    luma = (
        rgb[:, :, 0] * 0.299
        + rgb[:, :, 1] * 0.587
        + rgb[:, :, 2] * 0.114
    )
    chroma = np.max(rgb, axis=2) - np.min(rgb, axis=2)
    face_core_mask = face_mask >= 32
    replace_candidate_mask = (
        (alpha >= 12)
        & (luma >= 50.0)
        & (chroma <= 165.0)
    )
    replace_mask = face_core_mask & replace_candidate_mask
    if not bool(np.any(replace_mask)):
        return warped_patch

    replaced = warped_rgba.copy()
    asset_rgb = warped_rgba[:, :, :3]
    base_rgb = base_rgba[:, :, :3]
    replacement_color = None
    if skin_replacement_color_rgb is not None:
        replacement_color_array = np.asarray(skin_replacement_color_rgb, dtype=np.float32).reshape(-1)
        if replacement_color_array.size >= 3 and bool(np.all(np.isfinite(replacement_color_array[:3]))):
            replacement_color = np.clip(replacement_color_array[:3], 0.0, 255.0).astype(np.uint8)
    if replacement_color is not None:
        replaced[:, :, :3][replace_mask] = replacement_color
        return Image.fromarray(replaced, mode="RGBA")
    asset_ycrcb = cv2.cvtColor(asset_rgb, cv2.COLOR_RGB2YCrCb).astype(np.float32)
    base_ycrcb = cv2.cvtColor(base_rgb, cv2.COLOR_RGB2YCrCb).astype(np.float32)
    matched_ycrcb = asset_ycrcb.copy()
    matched_ycrcb[:, :, 0][replace_mask] = (
        asset_ycrcb[:, :, 0][replace_mask] * 0.35
        + base_ycrcb[:, :, 0][replace_mask] * 0.65
    )
    matched_ycrcb[:, :, 1][replace_mask] = (
        base_ycrcb[:, :, 1][replace_mask] * 0.95
        + asset_ycrcb[:, :, 1][replace_mask] * 0.05
    )
    matched_ycrcb[:, :, 2][replace_mask] = (
        base_ycrcb[:, :, 2][replace_mask] * 0.95
        + asset_ycrcb[:, :, 2][replace_mask] * 0.05
    )
    matched_rgb = cv2.cvtColor(
        np.clip(matched_ycrcb, 0.0, 255.0).astype(np.uint8),
        cv2.COLOR_YCrCb2RGB,
    )
    replaced[:, :, :3][replace_mask] = matched_rgb[replace_mask]
    return Image.fromarray(replaced, mode="RGBA")


def compose_bundle_frame(
    frame_image: Image.Image,
    bundle: AssetBundle | None,
    *,
    reference_width: int | None = None,
    reference_height: int | None = None,
    rgb_gain: float | None = None,
    original_frame_image: Image.Image | None = None,
    skin_replacement_color_rgb: np.ndarray | None = None,
    preserve_uncovered_base: bool = True,
    coverage_feather_px: int | None = None,
    debug_payload: dict[str, object] | None = None,
) -> Image.Image:
    if (
        bundle is None
        or bundle.hair_rgba_path is None
        or bundle.render_task is None
        or bundle.hair_bbox is None
    ):
        return frame_image

    timings_ms: dict[str, object] = {}
    compose_started_at = time.perf_counter()

    scale_render_task_started_at = time.perf_counter()
    render_task = bundle.render_task
    if reference_width is not None and reference_height is not None:
        render_task = _scale_render_task(
            render_task,
            reference_width=reference_width,
            reference_height=reference_height,
            frame_width=frame_image.width,
            frame_height=frame_image.height,
        )
    timings_ms["scale_render_task_ms"] = round((time.perf_counter() - scale_render_task_started_at) * 1000.0, 3)
    destination_roi = render_task.get("destination_roi")
    matrix = render_task.get("matrix")
    if not destination_roi or not matrix:
        return frame_image

    roi_width = int(destination_roi["w"])
    roi_height = int(destination_roi["h"])
    if roi_width <= 0 or roi_height <= 0:
        return frame_image

    rgba_cache_info_before = _load_rgba_image.cache_info()
    rgba_load_started_at = time.perf_counter()
    source_patch = _load_rgba_image(str(bundle.hair_rgba_path))
    timings_ms["rgba_load_ms"] = round((time.perf_counter() - rgba_load_started_at) * 1000.0, 3)
    timings_ms["rgba_cache_hit"] = _load_rgba_image.cache_info().hits > rgba_cache_info_before.hits
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

    inverse_started_at = time.perf_counter()
    inverse = _invert_affine(
        float(matrix["a"]),
        float(matrix["b"]),
        float(matrix["c"]),
        float(matrix["d"]),
        local_e,
        local_f,
    )
    timings_ms["inverse_affine_ms"] = round((time.perf_counter() - inverse_started_at) * 1000.0, 3)
    if inverse is None:
        return frame_image

    warp_started_at = time.perf_counter()
    warped_patch = source_patch.transform(
        (roi_width, roi_height),
        Image.AFFINE,
        inverse,
        resample=RESAMPLE_FILTER,
    )
    timings_ms["warp_patch_ms"] = round((time.perf_counter() - warp_started_at) * 1000.0, 3)
    rgb_gain_started_at = time.perf_counter()
    if rgb_gain is not None:
        warped_patch = _apply_rgba_rgb_gain(warped_patch, float(rgb_gain))
    timings_ms["rgb_gain_ms"] = round((time.perf_counter() - rgb_gain_started_at) * 1000.0, 3)
    coverage_started_at = time.perf_counter()
    warped_rgba = np.asarray(warped_patch, dtype=np.uint8)
    hard_coverage_mask = None
    if warped_rgba.ndim == 3 and warped_rgba.shape[2] == 4:
        hard_coverage_mask = np.where(warped_rgba[:, :, 3] >= 4, np.uint8(255), np.uint8(0))
        if int(np.count_nonzero(hard_coverage_mask)) > 0:
            hard_coverage_mask = cv2.dilate(
                hard_coverage_mask,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
                iterations=1,
            )
    timings_ms["coverage_mask_ms"] = round((time.perf_counter() - coverage_started_at) * 1000.0, 3)

    output = frame_image if frame_image.mode == "RGB" else frame_image.convert("RGB")
    box = (
        int(destination_roi["x"]),
        int(destination_roi["y"]),
        int(destination_roi["x"]) + roi_width,
        int(destination_roi["y"]) + roi_height,
    )
    base_crop_started_at = time.perf_counter()
    base_roi = output.crop(box).convert("RGBA")
    timings_ms["base_roi_crop_ms"] = round((time.perf_counter() - base_crop_started_at) * 1000.0, 3)
    restore_base_ms = 0.0
    if preserve_uncovered_base and original_frame_image is not None:
        original_output = (
            original_frame_image
            if original_frame_image.mode == "RGB"
            else original_frame_image.convert("RGB")
        )
        if original_output.size == output.size:
            original_roi = original_output.crop(box).convert("RGBA")
            restore_base_started_at = time.perf_counter()
            base_roi = _restore_uncovered_base_roi(
                base_roi,
                original_roi,
                warped_patch,
                feather_px=coverage_feather_px,
            )
            restore_base_ms = round((time.perf_counter() - restore_base_started_at) * 1000.0, 3)
    timings_ms["restore_uncovered_base_ms"] = restore_base_ms
    face_mask_path = getattr(bundle, "face_mask_path", None)
    protect_face_mask_path = getattr(bundle, "protect_face_mask_path", None)
    hair_bbox = getattr(bundle, "hair_bbox", None)
    skin_replace_debug_payload: dict[str, object] = {}
    skin_replace_started_at = time.perf_counter()
    warped_patch = _replace_asset_skin_with_base_roi(
        warped_patch,
        base_roi,
        skin_replacement_color_rgb=skin_replacement_color_rgb,
        face_mask_path=face_mask_path,
        protect_face_mask_path=protect_face_mask_path,
        hair_bbox=hair_bbox,
        inverse=inverse,
        roi_width=roi_width,
        roi_height=roi_height,
        debug_payload=skin_replace_debug_payload,
    )
    timings_ms["mask_load_ms"] = round(float(skin_replace_debug_payload.get("mask_load_ms", 0.0) or 0.0), 3)
    timings_ms["mask_load_count"] = int(skin_replace_debug_payload.get("mask_load_count", 0) or 0)
    timings_ms["mask_cache_hits"] = int(skin_replace_debug_payload.get("mask_cache_hits", 0) or 0)
    timings_ms["skin_replace_ms"] = round((time.perf_counter() - skin_replace_started_at) * 1000.0, 3)
    alpha_started_at = time.perf_counter()
    composited_roi = Image.alpha_composite(base_roi, warped_patch)
    timings_ms["alpha_composite_ms"] = round((time.perf_counter() - alpha_started_at) * 1000.0, 3)
    paste_started_at = time.perf_counter()
    output.paste(composited_roi.convert(output.mode), box[:2])
    timings_ms["paste_ms"] = round((time.perf_counter() - paste_started_at) * 1000.0, 3)
    timings_ms["total_ms"] = round((time.perf_counter() - compose_started_at) * 1000.0, 3)
    if debug_payload is not None:
        full_frame_coverage = np.zeros((output.height, output.width), dtype=np.uint8)
        if hard_coverage_mask is not None:
            full_frame_coverage[box[1] : box[3], box[0] : box[2]] = hard_coverage_mask
        debug_payload["coverage_mask"] = full_frame_coverage
        debug_payload["timings_ms"] = timings_ms
    return output
