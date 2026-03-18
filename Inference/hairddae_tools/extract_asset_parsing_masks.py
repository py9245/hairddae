#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image
import torchvision.transforms as transforms

from local_demo_paths import (
    default_face_parsing_repo_dir,
    default_face_parsing_weights,
    load_manifest_items,
    read_json,
    resolve_asset_path,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract BiSeNet parsing masks and derived asset masks.")
    parser.add_argument("--asset-root", required=True)
    parser.add_argument(
        "--repo-dir",
        default=str(default_face_parsing_repo_dir()),
    )
    parser.add_argument(
        "--weights",
        default=str(default_face_parsing_weights()),
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--mask-pipeline-version", default="bisenet_mask_v3")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-current-version", action="store_true")
    return parser.parse_args()

def save_mask(path: Path, mask: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), mask)


def save_rgba(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)


def save_prob_map(path: Path, prob: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = np.clip(np.round(prob * 255.0), 0, 255).astype(np.uint8)
    cv2.imwrite(str(path), normalized)


def binary_mask(parsing: np.ndarray, labels: set[int]) -> np.ndarray:
    return np.where(np.isin(parsing, list(labels)), 255, 0).astype(np.uint8)


def build_soft_alpha(hair_mask: np.ndarray, hair_confidence: np.ndarray) -> np.ndarray:
    confidence_alpha = np.clip(np.round(hair_confidence * 255.0), 0, 255).astype(np.uint8)
    confidence_alpha = np.where(dilate(hair_mask, 5) > 0, confidence_alpha, 0).astype(np.uint8)
    blurred = cv2.GaussianBlur(confidence_alpha, (0, 0), sigmaX=2.0, sigmaY=2.0)
    return np.maximum(hair_mask, blurred)


def build_soft_alpha_with_suppression(
    hair_mask: np.ndarray,
    hair_confidence: np.ndarray,
    suppression_mask: np.ndarray | None = None,
    preserve_mask: np.ndarray | None = None,
) -> np.ndarray:
    base_alpha = build_soft_alpha(hair_mask, hair_confidence)
    alpha = base_alpha.copy()
    if suppression_mask is None or np.count_nonzero(suppression_mask) == 0:
        return alpha
    active_suppression = cv2.bitwise_and(suppression_mask, dilate(hair_mask, 5))
    suppression_strength = cv2.GaussianBlur(
        (active_suppression > 0).astype(np.float32),
        (0, 0),
        sigmaX=2.8,
        sigmaY=2.8,
    )
    if preserve_mask is not None and np.count_nonzero(preserve_mask) > 0:
        preserve_strength = cv2.GaussianBlur(
            (preserve_mask > 16).astype(np.float32),
            (0, 0),
            sigmaX=3.0,
            sigmaY=3.0,
        )
        suppression_strength = np.clip(suppression_strength * (1.0 - 0.90 * preserve_strength), 0.0, 1.0)
    gain = np.clip(1.0 - 0.62 * suppression_strength, 0.42, 1.0)
    alpha = np.clip(alpha.astype(np.float32) * gain, 0.0, 255.0).astype(np.uint8)
    if preserve_mask is not None and np.count_nonzero(preserve_mask) > 0:
        preserve_binary = np.where(preserve_mask > 16, 255, 0).astype(np.uint8)
        preserved_alpha = cv2.bitwise_and(base_alpha, preserve_binary)
        alpha = np.maximum(alpha, cv2.GaussianBlur(preserved_alpha, (0, 0), sigmaX=1.0, sigmaY=1.0))
    return cv2.GaussianBlur(alpha, (0, 0), sigmaX=1.2, sigmaY=1.2)


def dilate(mask: np.ndarray, ksize: int) -> np.ndarray:
    kernel = np.ones((ksize, ksize), np.uint8)
    return cv2.dilate(mask, kernel, iterations=1)


def mask_area_ratio(mask: np.ndarray) -> float:
    return float(np.count_nonzero(mask)) / float(mask.shape[0] * mask.shape[1])


def component_count(mask: np.ndarray, min_area: int = 64) -> int:
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    count = 0
    for label_idx in range(1, n_labels):
        if int(stats[label_idx, cv2.CC_STAT_AREA]) >= min_area:
            count += 1
    return count


def boundary_touches(mask: np.ndarray, margin: int = 2) -> dict[str, bool]:
    return {
        "top": bool(np.count_nonzero(mask[:margin, :]) > 0),
        "bottom": bool(np.count_nonzero(mask[-margin:, :]) > 0),
        "left": bool(np.count_nonzero(mask[:, :margin]) > 0),
        "right": bool(np.count_nonzero(mask[:, -margin:]) > 0),
    }


def head_detail_band(shape: tuple[int, int], face_bbox: dict[str, Any]) -> np.ndarray:
    height, width = shape
    band = np.zeros((height, width), dtype=np.uint8)
    if not face_bbox or face_bbox.get("w") in (None, 0) or face_bbox.get("h") in (None, 0):
        return band
    x0 = max(0, int(round(face_bbox["x"] - face_bbox["w"] * 0.35)))
    x1 = min(width, int(round(face_bbox["x"] + face_bbox["w"] * 1.35)))
    y0 = max(0, int(round(face_bbox["y"] - face_bbox["h"] * 0.65)))
    y1 = min(height, int(round(face_bbox["y"] + face_bbox["h"] * 0.35)))
    if x1 > x0 and y1 > y0:
        band[y0:y1, x0:x1] = 255
    return band


def empty_mask_like(mask: np.ndarray) -> np.ndarray:
    return np.zeros_like(mask, dtype=np.uint8)


def _point_xy(anchors: dict[str, Any], name: str) -> tuple[float | None, float | None]:
    point = anchors.get(name, {})
    return point.get("x"), point.get("y")


def build_fringe_keep_mask(
    shape: tuple[int, int],
    face_bbox: dict[str, Any] | None,
    anchors: dict[str, Any],
) -> np.ndarray:
    keep = np.zeros(shape, dtype=np.uint8)
    if not face_bbox or face_bbox.get("w") in (None, 0) or face_bbox.get("h") in (None, 0):
        return keep

    width = float(face_bbox["w"])
    height = float(face_bbox["h"])
    left_temple_x, _ = _point_xy(anchors, "left_temple")
    right_temple_x, _ = _point_xy(anchors, "right_temple")
    _, forehead_y = _point_xy(anchors, "forehead_center")
    _, crown_y = _point_xy(anchors, "crown")
    if any(value is None for value in [left_temple_x, right_temple_x, forehead_y]):
        return keep

    center_x = int(round((float(left_temple_x) + float(right_temple_x)) * 0.5))
    center_y = int(round((float(forehead_y) + float(crown_y if crown_y is not None else forehead_y)) * 0.5))
    axes = (
        max(14, int(round(width * 0.38))),
        max(12, int(round(height * 0.24))),
    )
    cv2.ellipse(keep, (center_x, center_y), axes, 0, 0, 360, 255, -1)

    y0 = max(0, int(round(float(face_bbox["y"]) - height * 0.05)))
    y1 = min(shape[0], int(round(float(forehead_y) + height * 0.20)))
    x0 = max(0, int(round(min(float(left_temple_x), float(right_temple_x)) - width * 0.12)))
    x1 = min(shape[1], int(round(max(float(left_temple_x), float(right_temple_x)) + width * 0.12)))
    if x1 > x0 and y1 > y0:
        keep[y0:y1, x0:x1] = 255
    return cv2.GaussianBlur(keep, (0, 0), sigmaX=2.8, sigmaY=2.8)


def build_overlap_suppression_mask(
    face_mask: np.ndarray,
    ear_left: np.ndarray,
    ear_right: np.ndarray,
    anchors: dict[str, Any],
    face_bbox: dict[str, Any] | None,
) -> np.ndarray:
    suppression = empty_mask_like(face_mask)
    if not face_bbox or face_bbox.get("w") in (None, 0) or face_bbox.get("h") in (None, 0):
        return suppression

    height, width = face_mask.shape
    face_x = float(face_bbox["x"])
    face_y = float(face_bbox["y"])
    face_w = float(face_bbox["w"])
    face_h = float(face_bbox["h"])
    left_side_x, _ = _point_xy(anchors, "left_side")
    right_side_x, _ = _point_xy(anchors, "right_side")
    lower_left_x, lower_left_y = _point_xy(anchors, "lower_left")
    lower_right_x, lower_right_y = _point_xy(anchors, "lower_right")

    face_skin = dilate(face_mask, 2)
    ear_skin = dilate(cv2.bitwise_or(ear_left, ear_right), 4)

    left_band = empty_mask_like(face_mask)
    left_x1 = int(round((float(left_side_x) if left_side_x is not None else face_x + face_w * 0.28) + face_w * 0.03))
    left_x1 = min(width, max(0, left_x1))
    left_y0 = max(0, int(round(face_y + face_h * 0.28)))
    left_y1 = min(height, int(round(face_y + face_h * 0.98)))
    if left_x1 > 0 and left_y1 > left_y0:
        left_band[left_y0:left_y1, 0:left_x1] = 255

    right_band = empty_mask_like(face_mask)
    right_x0 = int(round((float(right_side_x) if right_side_x is not None else face_x + face_w * 0.72) - face_w * 0.03))
    right_x0 = min(width, max(0, right_x0))
    right_y0 = max(0, int(round(face_y + face_h * 0.28)))
    right_y1 = min(height, int(round(face_y + face_h * 0.98)))
    if width > right_x0 and right_y1 > right_y0:
        right_band[right_y0:right_y1, right_x0:width] = 255

    lower_center = empty_mask_like(face_mask)
    lower_x0 = max(0, int(round(face_x + face_w * 0.40)))
    lower_x1 = min(width, int(round(face_x + face_w * 0.60)))
    lower_y_anchor = max(
        float(lower_left_y) if lower_left_y is not None else face_y + face_h * 0.78,
        float(lower_right_y) if lower_right_y is not None else face_y + face_h * 0.78,
    )
    lower_y0 = max(0, int(round(lower_y_anchor - face_h * 0.01)))
    lower_y1 = min(height, int(round(face_y + face_h * 0.98)))
    if lower_x1 > lower_x0 and lower_y1 > lower_y0:
        lower_center[lower_y0:lower_y1, lower_x0:lower_x1] = 255

    jaw_wings = empty_mask_like(face_mask)
    if lower_left_x is not None and lower_left_y is not None:
        cv2.ellipse(
            jaw_wings,
            (int(round(float(lower_left_x))), int(round(float(lower_left_y) - face_h * 0.02))),
            (max(4, int(round(face_w * 0.08))), max(6, int(round(face_h * 0.09)))),
            0,
            120,
            250,
            255,
            -1,
        )
    if lower_right_x is not None and lower_right_y is not None:
        cv2.ellipse(
            jaw_wings,
            (int(round(float(lower_right_x))), int(round(float(lower_right_y) - face_h * 0.02))),
            (max(4, int(round(face_w * 0.08))), max(6, int(round(face_h * 0.09)))),
            0,
            -70,
            60,
            255,
            -1,
        )

    lateral_skin = cv2.bitwise_and(face_skin, cv2.bitwise_or(left_band, right_band))
    lower_skin = cv2.bitwise_and(face_skin, cv2.bitwise_or(lower_center, jaw_wings))
    suppression = cv2.bitwise_or(ear_skin, cv2.bitwise_or(lateral_skin, lower_skin))

    fringe_keep = build_fringe_keep_mask(face_mask.shape, face_bbox, anchors)
    if np.count_nonzero(fringe_keep) > 0:
        fringe_protect = dilate(np.where(fringe_keep > 16, 255, 0).astype(np.uint8), 9)
        suppression = cv2.bitwise_and(suppression, cv2.bitwise_not(fringe_protect))
    suppression = cv2.morphologyEx(suppression, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    return cv2.morphologyEx(suppression, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)


def interior_hole_mask(mask: np.ndarray, min_area: int = 12) -> np.ndarray:
    if mask is None or mask.size == 0 or np.count_nonzero(mask) == 0:
        return np.zeros_like(mask, dtype=np.uint8)
    binary = (mask > 0).astype(np.uint8)
    inverse = (1 - binary).astype(np.uint8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inverse, connectivity=8)
    holes = np.zeros_like(mask, dtype=np.uint8)
    height, width = mask.shape[:2]
    for label_idx in range(1, num_labels):
        x = int(stats[label_idx, cv2.CC_STAT_LEFT])
        y = int(stats[label_idx, cv2.CC_STAT_TOP])
        w = int(stats[label_idx, cv2.CC_STAT_WIDTH])
        h = int(stats[label_idx, cv2.CC_STAT_HEIGHT])
        area = int(stats[label_idx, cv2.CC_STAT_AREA])
        touches_border = x <= 0 or y <= 0 or (x + w) >= width or (y + h) >= height
        if touches_border or area < min_area:
            continue
        holes[labels == label_idx] = 255
    return holes


def fill_small_holes(mask: np.ndarray, max_area: int) -> np.ndarray:
    holes = interior_hole_mask(mask, min_area=1)
    if np.count_nonzero(holes) == 0:
        return mask
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats((holes > 0).astype(np.uint8), connectivity=8)
    filled = mask.copy()
    for label_idx in range(1, num_labels):
        area = int(stats[label_idx, cv2.CC_STAT_AREA])
        if area <= max_area:
            filled[labels == label_idx] = 255
    return filled


def build_mask_preview(
    image_bgr: np.ndarray,
    hair_mask: np.ndarray,
    alpha: np.ndarray,
    face_bbox: dict[str, Any] | None,
    failure_tags: list[str],
) -> np.ndarray:
    preview = image_bgr.copy()
    overlay = np.zeros_like(preview)
    overlay[:, :, 1] = 220
    mask_region = hair_mask > 0
    preview[mask_region] = cv2.addWeighted(preview, 0.40, overlay, 0.60, 0.0)[mask_region]

    alpha_edges = cv2.Canny(alpha, 32, 96)
    preview[alpha_edges > 0] = (0, 255, 255)

    if face_bbox and face_bbox.get("w") and face_bbox.get("h"):
        x0 = int(face_bbox["x"])
        y0 = int(face_bbox["y"])
        x1 = x0 + int(face_bbox["w"])
        y1 = y0 + int(face_bbox["h"])
        cv2.rectangle(preview, (x0, y0), (x1, y1), (255, 180, 0), 2)

    if failure_tags:
        for row_idx, tag in enumerate(failure_tags[:5], start=1):
            cv2.putText(
                preview,
                tag,
                (12, 24 * row_idx),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )
    return preview


def detect_failure_tags(
    hair_mask: np.ndarray,
    face_mask: np.ndarray,
    alpha: np.ndarray,
    hair_confidence: np.ndarray,
    face_bbox: dict[str, Any] | None,
    anchors: dict[str, Any] | None = None,
    ear_left: np.ndarray | None = None,
    ear_right: np.ndarray | None = None,
) -> list[str]:
    tags: list[str] = []
    hair_area = mask_area_ratio(hair_mask)
    touches = boundary_touches(hair_mask)
    components = component_count(hair_mask)
    mask_pixels = max(1, np.count_nonzero(hair_mask))
    face_overlap = np.count_nonzero(cv2.bitwise_and(hair_mask, dilate(face_mask, 3)))
    soft_edge_pixels = np.count_nonzero((alpha > 0) & (alpha < 220))
    masked_confidence = hair_confidence[hair_mask > 0]
    mean_confidence = float(masked_confidence.mean()) if masked_confidence.size else 0.0
    hole_mask = interior_hole_mask(hair_mask, min_area=12)
    hole_pixels = int(np.count_nonzero(hole_mask))
    hole_ratio = hole_pixels / float(mask_pixels)

    if hair_area < 0.002:
        tags.append("empty_mask")
    if touches["top"]:
        tags.append("top_cut_risk")
    if touches["left"] or touches["right"]:
        tags.append("side_cut_risk")
    if components >= 4:
        tags.append("fragmented_mask")
    if hole_pixels >= max(18, int(mask_pixels * 0.003)) and hole_ratio >= 0.0006:
        tags.append("internal_hole_risk")
    if face_overlap / float(mask_pixels) >= 0.16:
        tags.append("face_overlap_risk")
    if mean_confidence < 0.45:
        tags.append("low_confidence")
    if soft_edge_pixels / float(mask_pixels) < 0.03:
        tags.append("hard_edge_risk")

    if anchors is not None and ear_left is not None and ear_right is not None:
        suppression_mask = build_overlap_suppression_mask(
            face_mask=face_mask,
            ear_left=ear_left,
            ear_right=ear_right,
            anchors=anchors,
            face_bbox=face_bbox,
        )
        suppression_overlap = np.count_nonzero(cv2.bitwise_and(hair_mask, suppression_mask))
        if suppression_overlap / float(mask_pixels) >= 0.04:
            tags.append("side_skin_overlap_risk")
        if face_bbox and face_bbox.get("w") and face_bbox.get("h"):
            fringe_keep = np.where(build_fringe_keep_mask(hair_mask.shape, face_bbox, anchors) > 16, 255, 0).astype(np.uint8)
            fringe_area = max(1, int(np.count_nonzero(fringe_keep)))
            fringe_fill_ratio = np.count_nonzero(cv2.bitwise_and(hair_mask, fringe_keep)) / float(fringe_area)
            if fringe_fill_ratio < 0.22 and face_overlap / float(mask_pixels) < 0.12:
                tags.append("fringe_cut_risk")

    detail_band = head_detail_band(hair_mask.shape, face_bbox or {})
    wispy_candidates = (
        (hair_confidence >= 0.12)
        & (hair_confidence < 0.50)
        & (detail_band > 0)
        & (dilate(hair_mask, 9) > 0)
        & (hair_mask == 0)
    )
    if np.count_nonzero(wispy_candidates) >= max(32, int(mask_pixels * 0.05)):
        tags.append("wispy_loss_risk")

    return tags


def anchor_seed_mask(shape: tuple[int, int], anchors: dict[str, Any], face_bbox: dict[str, Any]) -> np.ndarray:
    height, width = shape
    seed = np.zeros((height, width), dtype=np.uint8)
    if not face_bbox or face_bbox.get("w") in (None, 0) or face_bbox.get("h") in (None, 0):
        return seed
    radius = max(8, int(round(face_bbox["w"] * 0.10)))
    seed_names = ["crown", "forehead_center", "left_temple", "right_temple", "left_side", "right_side", "lower_left", "lower_right"]
    for name in seed_names:
        point = anchors.get(name, {})
        x = point.get("x")
        y = point.get("y")
        if x is None or y is None:
            continue
        cv2.circle(seed, (int(round(x)), int(round(y))), radius, 255, -1)
    return seed


def refine_hair_mask(
    hair_mask: np.ndarray,
    face_mask: np.ndarray,
    ear_left: np.ndarray,
    ear_right: np.ndarray,
    neck_mask: np.ndarray,
    anchors: dict[str, Any],
    face_bbox: dict[str, Any],
) -> np.ndarray:
    if np.count_nonzero(hair_mask) == 0:
        return hair_mask

    original_hair = hair_mask.copy()
    fringe_keep = np.where(build_fringe_keep_mask(hair_mask.shape, face_bbox, anchors) > 16, 255, 0).astype(np.uint8)
    seed = anchor_seed_mask(hair_mask.shape, anchors, face_bbox)
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats((hair_mask > 0).astype(np.uint8), connectivity=8)
    refined = np.zeros_like(hair_mask)
    min_area = max(32, int(round(face_bbox["w"] * face_bbox["h"] * 0.01))) if face_bbox and face_bbox.get("w") else 32

    for label_idx in range(1, n_labels):
        component = np.where(labels == label_idx, 255, 0).astype(np.uint8)
        area = int(stats[label_idx, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        touches_seed = np.count_nonzero(cv2.bitwise_and(component, seed)) > 0
        if not touches_seed:
            continue
        refined = cv2.bitwise_or(refined, component)

    # neck-only blobs are not valid hair. remove region dominated by neck.
    refined = cv2.bitwise_and(refined, cv2.bitwise_not(dilate(neck_mask, 7)))

    # Keep face-center intrusion low while leaving fringe around forehead.
    if face_bbox and face_bbox.get("w"):
        face_core = np.zeros_like(face_mask)
        center = (int(round(face_bbox["x"] + face_bbox["w"] * 0.5)), int(round(face_bbox["y"] + face_bbox["h"] * 0.72)))
        axes = (int(round(face_bbox["w"] * 0.14)), int(round(face_bbox["h"] * 0.16)))
        cv2.ellipse(face_core, center, axes, 0, 0, 360, 255, -1)
        refined = cv2.bitwise_and(refined, cv2.bitwise_not(face_core))

    overlap_suppression = build_overlap_suppression_mask(
        face_mask=face_mask,
        ear_left=ear_left,
        ear_right=ear_right,
        anchors=anchors,
        face_bbox=face_bbox,
    )
    protected_suppression = cv2.bitwise_and(
        overlap_suppression,
        cv2.bitwise_not(dilate(fringe_keep, 7)),
    )
    refined = cv2.bitwise_and(refined, cv2.bitwise_not(protected_suppression))
    refined = cv2.bitwise_or(refined, cv2.bitwise_and(original_hair, dilate(fringe_keep, 3)))

    refined = cv2.morphologyEx(refined, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=1)
    max_hole_area = max(24, int(round(face_bbox["w"] * face_bbox["h"] * 0.006))) if face_bbox and face_bbox.get("w") else 48
    refined = fill_small_holes(refined, max_hole_area)
    refined = cv2.morphologyEx(refined, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    refined = fill_small_holes(refined, max(12, max_hole_area // 2))
    refined = cv2.bitwise_or(refined, cv2.bitwise_and(original_hair, fringe_keep))
    return refined


def compute_forehead_mask(
    skin_mask: np.ndarray,
    face_bbox: dict[str, Any],
    anchors: dict[str, Any],
) -> np.ndarray:
    forehead = np.zeros_like(skin_mask)
    if not face_bbox or face_bbox.get("w") in (None, 0) or face_bbox.get("h") in (None, 0):
        return forehead

    left = anchors.get("left_temple", {})
    right = anchors.get("right_temple", {})
    center = anchors.get("forehead_center", {})
    if any(value is None for value in [left.get("x"), right.get("x"), center.get("y")]):
        return forehead

    x0 = int(max(0, min(left["x"], right["x"])))
    x1 = int(min(skin_mask.shape[1], max(left["x"], right["x"])))
    y0 = int(max(0, face_bbox["y"]))
    y1 = int(min(skin_mask.shape[0], center["y"] + face_bbox["h"] * 0.18))
    if x1 <= x0 or y1 <= y0:
        return forehead

    forehead[y0:y1, x0:x1] = 255
    return cv2.bitwise_and(forehead, skin_mask)


def mask_bbox(mask: np.ndarray) -> dict[str, int] | None:
    ys, xs = np.where(mask > 0)
    if xs.size == 0 or ys.size == 0:
        return None
    x0 = int(xs.min())
    y0 = int(ys.min())
    x1 = int(xs.max())
    y1 = int(ys.max())
    return {"x": x0, "y": y0, "w": x1 - x0 + 1, "h": y1 - y0 + 1}


def expand_bbox(bbox: dict[str, int], width: int, height: int, margin: int) -> dict[str, int]:
    x0 = max(0, bbox["x"] - margin)
    y0 = max(0, bbox["y"] - margin)
    x1 = min(width, bbox["x"] + bbox["w"] + margin)
    y1 = min(height, bbox["y"] + bbox["h"] + margin)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def build_hair_rgba(
    image_bgr: np.ndarray,
    alpha: np.ndarray,
    bbox: dict[str, int] | None,
    margin: int = 16,
) -> tuple[np.ndarray, dict[str, int] | None]:
    if bbox is None:
        return np.zeros((1, 1, 4), dtype=np.uint8), None

    height, width = image_bgr.shape[:2]
    crop_bbox = expand_bbox(bbox, width, height, margin)
    x0 = crop_bbox["x"]
    y0 = crop_bbox["y"]
    x1 = x0 + crop_bbox["w"]
    y1 = y0 + crop_bbox["h"]
    cropped_bgr = image_bgr[y0:y1, x0:x1]
    cropped_alpha = alpha[y0:y1, x0:x1]
    # OpenCV writes 4-channel PNGs as BGRA. The asset is conceptually RGBA with the saved alpha.
    return np.dstack([cropped_bgr, cropped_alpha]), crop_bbox


def expanded_head_roi(face_bbox: dict[str, Any], width: int, height: int) -> tuple[int, int, int, int]:
    x = face_bbox["x"]
    y = face_bbox["y"]
    w = face_bbox["w"]
    h = face_bbox["h"]

    cx = x + w / 2.0
    roi_w = min(width, max(int(round(w * 2.8)), int(round(width * 0.62))))
    roi_h = min(height, max(int(round(h * 3.2)), int(round(height * 0.40))))

    x0 = int(round(cx - roi_w / 2.0))
    y0 = int(round(y - h * 0.85))
    x0 = max(0, min(width - roi_w, x0))
    y0 = max(0, min(height - roi_h, y0))
    return x0, y0, roi_w, roi_h


def main() -> None:
    args = parse_args()
    asset_root = Path(args.asset_root).resolve()
    repo_dir = Path(args.repo_dir).resolve()
    if not repo_dir.exists():
        raise FileNotFoundError(f"Missing repo dir: {repo_dir}")
    if not Path(args.weights).exists():
        raise FileNotFoundError(f"Missing weights: {args.weights}")

    sys.path.insert(0, str(repo_dir))
    from model import BiSeNet  # type: ignore

    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    rows = load_manifest_items(asset_root)
    if args.skip_current_version:
        filtered_rows: list[dict[str, Any]] = []
        for row in rows:
            metadata_path = resolve_asset_path(asset_root, row["metadata_path"])
            metadata = read_json(metadata_path)
            current_version = metadata.get("lineage", {}).get("mask_pipeline_version")
            if current_version == args.mask_pipeline_version:
                continue
            filtered_rows.append(row)
        rows = filtered_rows
    if args.limit > 0:
        rows = rows[: args.limit]

    net = BiSeNet(n_classes=19)
    state = torch.load(args.weights, map_location=device)
    net.load_state_dict(state)
    net.to(device)
    net.eval()

    to_tensor = transforms.Compose(
        [
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ]
    )

    label_skin = {1}
    label_ears_l = {7}
    label_ears_r = {8}
    label_face_core = {1, 2, 3, 4, 5, 6, 10, 11, 12, 13}
    label_neck = {14, 15, 16}
    # In this pretrained CelebAMask-HQ model, real hair can sometimes fall into the hat class.
    label_hair = {17, 18}

    updated = 0
    failed = 0
    failure_counter: Counter[str] = Counter()

    with torch.no_grad():
        for start in range(0, len(rows), args.batch_size):
            batch_rows = rows[start : start + args.batch_size]
            batch_tensors: list[torch.Tensor] = []
            batch_images: list[np.ndarray] = []
            batch_sizes: list[tuple[int, int]] = []

            for row in batch_rows:
                image_path = resolve_asset_path(asset_root, row["image_path"])
                metadata_path = resolve_asset_path(asset_root, row["metadata_path"])
                metadata = read_json(metadata_path)
                image_bgr = cv2.imread(str(image_path))
                face_bbox = metadata.get("face_bbox")
                if image_bgr is None or not face_bbox or face_bbox.get("w") in (None, 0) or face_bbox.get("h") in (None, 0):
                    batch_tensors.append(None)  # type: ignore[arg-type]
                    batch_images.append(None)  # type: ignore[arg-type]
                    batch_sizes.append((0, 0))
                    continue
                width, height = image_bgr.shape[1], image_bgr.shape[0]
                x0, y0, roi_w, roi_h = expanded_head_roi(face_bbox, width, height)
                roi_bgr = image_bgr[y0 : y0 + roi_h, x0 : x0 + roi_w]
                image_rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
                batch_images.append(image_bgr)
                batch_sizes.append((width, height, x0, y0, roi_w, roi_h))
                pil_image = Image.fromarray(image_rgb).resize((512, 512), Image.BILINEAR)
                batch_tensors.append(to_tensor(pil_image))

            valid_entries = [(idx, tensor) for idx, tensor in enumerate(batch_tensors) if tensor is not None]
            if not valid_entries:
                failed += len(batch_rows)
                continue

            tensor_batch = torch.stack([tensor for _, tensor in valid_entries], dim=0).to(device)
            out = net(tensor_batch)[0]
            parsing_batch = out.cpu().numpy().argmax(1)
            hair_confidence_batch = torch.softmax(out, dim=1)[:, 17:19].sum(dim=1).cpu().numpy()

            parsing_offset = 0
            for local_idx, row in enumerate(batch_rows):
                image_bgr = batch_images[local_idx]
                if image_bgr is None:
                    failed += 1
                    continue

                parsing_512 = parsing_batch[parsing_offset]
                parsing_offset += 1

                metadata_path = resolve_asset_path(asset_root, row["metadata_path"])
                metadata = read_json(metadata_path)
                metadata.setdefault("parsing_path", str(Path("parsing") / f"{metadata['asset_id']}.png"))
                metadata.setdefault("hair_confidence_path", str(Path("confidence") / "hair" / f"{metadata['asset_id']}.png"))
                metadata.setdefault("hair_rgba_path", str(Path("hair_rgba") / f"{metadata['asset_id']}.png"))
                metadata.setdefault("hair_rgba_bbox", None)
                metadata.setdefault("qa_mask_preview_path", str(Path("qa") / "mask_preview" / f"{metadata['asset_id']}.png"))
                metadata.setdefault("failure_tags", [])
                anchors_path = resolve_asset_path(asset_root, metadata["anchors_path"])
                anchors_payload = read_json(anchors_path)
                anchors = anchors_payload.get("anchors", {})

                width, height, x0, y0, roi_w, roi_h = batch_sizes[local_idx]
                parsing_roi = cv2.resize(parsing_512.astype(np.uint8), (roi_w, roi_h), interpolation=cv2.INTER_NEAREST)
                hair_confidence_roi = cv2.resize(
                    hair_confidence_batch[parsing_offset - 1].astype(np.float32),
                    (roi_w, roi_h),
                    interpolation=cv2.INTER_LINEAR,
                )
                parsing = np.zeros((height, width), dtype=np.uint8)
                hair_confidence = np.zeros((height, width), dtype=np.float32)
                parsing[y0 : y0 + roi_h, x0 : x0 + roi_w] = parsing_roi
                hair_confidence[y0 : y0 + roi_h, x0 : x0 + roi_w] = hair_confidence_roi

                hair_mask = binary_mask(parsing, label_hair)
                skin_mask = binary_mask(parsing, label_skin)
                face_mask = binary_mask(parsing, label_face_core)
                ear_left = binary_mask(parsing, label_ears_l)
                ear_right = binary_mask(parsing, label_ears_r)
                neck_shoulder = binary_mask(parsing, label_neck)
                overlap_suppression = build_overlap_suppression_mask(
                    face_mask=face_mask,
                    ear_left=ear_left,
                    ear_right=ear_right,
                    anchors=anchors,
                    face_bbox=metadata.get("face_bbox"),
                )
                hair_mask = refine_hair_mask(
                    hair_mask,
                    face_mask,
                    ear_left,
                    ear_right,
                    neck_shoulder,
                    anchors,
                    metadata.get("face_bbox"),
                )
                forehead_mask = compute_forehead_mask(skin_mask, metadata.get("face_bbox"), anchors)
                protect_face = cv2.bitwise_or(dilate(face_mask, 9), dilate(cv2.bitwise_or(ear_left, ear_right), 7))
                suppress_prior = cv2.bitwise_and(dilate(hair_mask, 11), cv2.bitwise_not(protect_face))
                preserve_mask = build_fringe_keep_mask(hair_mask.shape, metadata.get("face_bbox"), anchors)
                alpha = build_soft_alpha_with_suppression(
                    hair_mask,
                    hair_confidence,
                    overlap_suppression,
                    preserve_mask=preserve_mask,
                )
                hair_bbox = mask_bbox(hair_mask)
                hair_rgba, hair_rgba_bbox = build_hair_rgba(image_bgr, alpha, hair_bbox)
                failure_tags = detect_failure_tags(
                    hair_mask=hair_mask,
                    face_mask=face_mask,
                    alpha=alpha,
                    hair_confidence=hair_confidence,
                    face_bbox=metadata.get("face_bbox"),
                    anchors=anchors,
                    ear_left=ear_left,
                    ear_right=ear_right,
                )
                preview = build_mask_preview(
                    image_bgr=image_bgr,
                    hair_mask=hair_mask,
                    alpha=alpha,
                    face_bbox=metadata.get("face_bbox"),
                    failure_tags=failure_tags,
                )

                save_mask(resolve_asset_path(asset_root, metadata["parsing_path"]), parsing.astype(np.uint8))
                save_prob_map(resolve_asset_path(asset_root, metadata["hair_confidence_path"]), hair_confidence)
                save_mask(resolve_asset_path(asset_root, metadata["alpha_path"]), alpha)
                save_rgba(resolve_asset_path(asset_root, metadata["hair_rgba_path"]), hair_rgba)
                save_mask(resolve_asset_path(asset_root, metadata["hair_mask_path"]), hair_mask)
                save_mask(resolve_asset_path(asset_root, metadata["face_mask_path"]), face_mask)
                save_mask(resolve_asset_path(asset_root, metadata["ear_mask_left_path"]), ear_left)
                save_mask(resolve_asset_path(asset_root, metadata["ear_mask_right_path"]), ear_right)
                save_mask(resolve_asset_path(asset_root, metadata["forehead_mask_path"]), forehead_mask)
                save_mask(resolve_asset_path(asset_root, metadata["neck_shoulder_mask_path"]), neck_shoulder)
                save_mask(resolve_asset_path(asset_root, metadata["overlap_suppression_mask_path"]), overlap_suppression)
                save_mask(resolve_asset_path(asset_root, metadata["protect_face_mask_path"]), protect_face)
                save_mask(resolve_asset_path(asset_root, metadata["suppress_prior_mask_path"]), suppress_prior)
                save_rgba(resolve_asset_path(asset_root, metadata["qa_mask_preview_path"]), preview)

                for tag in failure_tags:
                    failure_preview_path = asset_root / "qa" / "failure_types" / tag / f"{metadata['asset_id']}.png"
                    save_rgba(failure_preview_path, preview)
                    failure_counter[tag] += 1

                if hair_bbox is not None:
                    metadata["hair_width_ratio"] = round(hair_bbox["w"] / float(width), 6)
                    metadata["hair_height_ratio"] = round(hair_bbox["h"] / float(height), 6)
                metadata["hair_rgba_bbox"] = hair_rgba_bbox
                metadata["hair_area_ratio"] = round(mask_area_ratio(hair_mask), 6)
                metadata["alpha_area_ratio"] = round(mask_area_ratio(alpha), 6)
                metadata["mask_component_count"] = component_count(hair_mask)
                metadata["mask_roi"] = {"x": x0, "y": y0, "w": roi_w, "h": roi_h}
                metadata["boundary_touches"] = boundary_touches(hair_mask)
                mask_pixels = max(1, np.count_nonzero(hair_mask))
                hole_mask = interior_hole_mask(hair_mask, min_area=12)
                hole_pixels = int(np.count_nonzero(hole_mask))
                metadata["hole_pixels"] = hole_pixels
                metadata["hole_ratio"] = round(hole_pixels / float(mask_pixels), 6)
                fringe_keep = np.where(preserve_mask > 16, 255, 0).astype(np.uint8)
                fringe_area = max(1, int(np.count_nonzero(fringe_keep)))
                metadata["fringe_fill_ratio"] = round(
                    np.count_nonzero(cv2.bitwise_and(hair_mask, fringe_keep)) / float(fringe_area),
                    6,
                )
                metadata["face_overlap_ratio"] = round(
                    np.count_nonzero(cv2.bitwise_and(hair_mask, dilate(face_mask, 3))) / float(mask_pixels),
                    6,
                )
                metadata["overlap_suppression_ratio"] = round(
                    np.count_nonzero(cv2.bitwise_and(hair_mask, overlap_suppression)) / float(mask_pixels),
                    6,
                )
                masked_confidence = hair_confidence[hair_mask > 0]
                if masked_confidence.size:
                    metadata["hair_mean_confidence"] = round(float(masked_confidence.mean()), 6)
                    metadata["hair_p90_confidence"] = round(float(np.percentile(masked_confidence, 90)), 6)
                else:
                    metadata["hair_mean_confidence"] = 0.0
                    metadata["hair_p90_confidence"] = 0.0
                metadata["failure_tags"] = failure_tags
                face_area = max(1, metadata["face_bbox"]["w"] * metadata["face_bbox"]["h"])
                metadata["forehead_visible_ratio"] = round(np.count_nonzero(forehead_mask) / face_area, 6)
                metadata["ear_visibility_left"] = round(np.count_nonzero(ear_left) / face_area, 6)
                metadata["ear_visibility_right"] = round(np.count_nonzero(ear_right) / face_area, 6)
                metadata["lineage"]["mask_pipeline_version"] = args.mask_pipeline_version
                write_json(metadata_path, metadata)
                updated += 1

    summary_path = asset_root / "manifests" / "mask_extraction_summary.json"
    write_json(
        summary_path,
        {
            "asset_root": str(asset_root),
            "repo_dir": str(repo_dir),
            "weights": str(Path(args.weights).resolve()),
            "device": str(device),
            "batch_size": args.batch_size,
            "mask_pipeline_version": args.mask_pipeline_version,
            "processed_rows": len(rows),
            "updated_rows": updated,
            "failed_rows": failed,
            "failure_tag_counts": dict(sorted(failure_counter.items())),
        },
    )


if __name__ == "__main__":
    main()
