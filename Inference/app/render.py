from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor
from typing import Any

from app.models import FeatureMessageModel


SOURCE_CROP_MARGIN = 16
DESTINATION_ROI_MARGIN = 12


@dataclass(frozen=True)
class Matrix2D:
    a: float
    b: float
    c: float
    d: float
    e: float
    f: float

    def to_message(self) -> dict[str, float]:
        return {
            "a": round(self.a, 6),
            "b": round(self.b, 6),
            "c": round(self.c, 6),
            "d": round(self.d, 6),
            "e": round(self.e, 6),
            "f": round(self.f, 6),
        }


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float

    def to_message(self) -> dict[str, float]:
        return {
            "x": round(self.x, 3),
            "y": round(self.y, 3),
        }


@dataclass(frozen=True)
class RenderTask:
    source_crop: dict[str, int]
    destination_roi: dict[str, int]
    destination_quad: tuple[Point2D, Point2D, Point2D, Point2D]
    matrix: Matrix2D

    def to_message(self) -> dict[str, Any]:
        return {
            "render_task_schema_version": 1,
            "mode": "affine_crop_v1",
            "source_crop": self.source_crop,
            "destination_roi": self.destination_roi,
            "destination_quad": [point.to_message() for point in self.destination_quad],
            "matrix": self.matrix.to_message(),
        }


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    size = len(matrix)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]

    for pivot in range(size):
        max_row = pivot
        for row in range(pivot + 1, size):
            if abs(augmented[row][pivot]) > abs(augmented[max_row][pivot]):
                max_row = row

        pivot_value = augmented[max_row][pivot]
        if abs(pivot_value) < 1e-8:
            return None

        if max_row != pivot:
            augmented[pivot], augmented[max_row] = augmented[max_row], augmented[pivot]

        for row in range(pivot + 1, size):
            factor = augmented[row][pivot] / augmented[pivot][pivot]
            for col in range(pivot, size + 1):
                augmented[row][col] -= factor * augmented[pivot][col]

    solution = [0.0] * size
    for row in range(size - 1, -1, -1):
        total = augmented[row][size]
        for col in range(row + 1, size):
            total -= augmented[row][col] * solution[col]
        solution[row] = total / augmented[row][row]

    return solution


def _estimate_similarity_transform(
    source_points: list[Point2D],
    destination_points: list[Point2D],
) -> Matrix2D | None:
    ata = [[0.0] * 4 for _ in range(4)]
    atb = [0.0] * 4

    for index, source in enumerate(source_points):
        destination = destination_points[index]
        rows = (
            [source.x, -source.y, 1.0, 0.0],
            [source.y, source.x, 0.0, 1.0],
        )
        outputs = (destination.x, destination.y)

        for row_index, row in enumerate(rows):
            output = outputs[row_index]
            for i in range(4):
                atb[i] += row[i] * output
                for j in range(4):
                    ata[i][j] += row[i] * row[j]

    solution = _solve_linear_system(ata, atb)
    if solution is None:
        return None

    a, b, tx, ty = solution
    return Matrix2D(a=a, b=b, c=-b, d=a, e=tx, f=ty)


def _estimate_affine_from_three_points(
    source_points: list[Point2D],
    destination_points: list[Point2D],
) -> Matrix2D | None:
    if len(source_points) < 3 or len(destination_points) < 3:
        return None

    matrix = [
        [source_points[0].x, source_points[0].y, 1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, source_points[0].x, source_points[0].y, 1.0],
        [source_points[1].x, source_points[1].y, 1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, source_points[1].x, source_points[1].y, 1.0],
        [source_points[2].x, source_points[2].y, 1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, source_points[2].x, source_points[2].y, 1.0],
    ]
    vector = [
        destination_points[0].x,
        destination_points[0].y,
        destination_points[1].x,
        destination_points[1].y,
        destination_points[2].x,
        destination_points[2].y,
    ]
    solution = _solve_linear_system(matrix, vector)
    if solution is None:
        return None

    a, c, e, b, d, f = solution
    return Matrix2D(a=a, b=b, c=c, d=d, e=e, f=f)


def _transform_point(matrix: Matrix2D, point: Point2D) -> Point2D:
    return Point2D(
        x=matrix.a * point.x + matrix.c * point.y + matrix.e,
        y=matrix.b * point.x + matrix.d * point.y + matrix.f,
    )


def _point_from_mapping(points: dict[str, Any], name: str) -> Point2D:
    point = points.get(name)
    if point is None:
        raise ValueError(f"missing anchor: {name}")
    return Point2D(x=float(point["x"]), y=float(point["y"]))


def _clamp_source_crop(
    image_size: dict[str, Any],
    hair_bbox: dict[str, Any],
) -> dict[str, int]:
    image_width = int(image_size["width"])
    image_height = int(image_size["height"])

    left = max(0, int(hair_bbox["x"]) - SOURCE_CROP_MARGIN)
    top = max(0, int(hair_bbox["y"]) - SOURCE_CROP_MARGIN)
    right = min(image_width, int(hair_bbox["x"]) + int(hair_bbox["w"]) + SOURCE_CROP_MARGIN)
    bottom = min(image_height, int(hair_bbox["y"]) + int(hair_bbox["h"]) + SOURCE_CROP_MARGIN)
    return {
        "x": left,
        "y": top,
        "w": max(0, right - left),
        "h": max(0, bottom - top),
    }


def _clamp_destination_roi(
    transformed_corners: tuple[Point2D, Point2D, Point2D, Point2D],
    frame_width: int,
    frame_height: int,
) -> dict[str, int] | None:
    left = max(0, floor(min(point.x for point in transformed_corners)) - DESTINATION_ROI_MARGIN)
    top = max(0, floor(min(point.y for point in transformed_corners)) - DESTINATION_ROI_MARGIN)
    right = min(frame_width, ceil(max(point.x for point in transformed_corners)) + DESTINATION_ROI_MARGIN)
    bottom = min(frame_height, ceil(max(point.y for point in transformed_corners)) + DESTINATION_ROI_MARGIN)
    if right <= left or bottom <= top:
        return None
    return {
        "x": int(left),
        "y": int(top),
        "w": int(right - left),
        "h": int(bottom - top),
    }


def build_render_task(
    *,
    feature: FeatureMessageModel,
    asset_anchors_payload: dict[str, Any],
    metadata: dict[str, Any],
) -> RenderTask | None:
    hair_bbox = metadata.get("hair_rgba_bbox")
    image_size = metadata.get("image_size")
    asset_anchors = asset_anchors_payload.get("anchors")
    if not hair_bbox or not image_size or not asset_anchors:
        return None

    source_points = [
        _point_from_mapping(asset_anchors, "left_temple"),
        _point_from_mapping(asset_anchors, "right_temple"),
        _point_from_mapping(asset_anchors, "forehead_center"),
        _point_from_mapping(asset_anchors, "crown"),
    ]
    destination_anchor_map = {
        name: point.model_dump() for name, point in feature.anchors.items()
    }
    destination_points = [
        _point_from_mapping(destination_anchor_map, "left_temple"),
        _point_from_mapping(destination_anchor_map, "right_temple"),
        _point_from_mapping(destination_anchor_map, "forehead_center"),
        _point_from_mapping(destination_anchor_map, "crown"),
    ]

    matrix = _estimate_similarity_transform(source_points, destination_points)
    if matrix is None:
        matrix = _estimate_affine_from_three_points(source_points[:3], destination_points[:3])
    if matrix is None:
        return None

    source_crop = _clamp_source_crop(image_size, hair_bbox)
    if source_crop["w"] <= 0 or source_crop["h"] <= 0:
        return None

    source_corners = (
        Point2D(x=float(source_crop["x"]), y=float(source_crop["y"])),
        Point2D(x=float(source_crop["x"] + source_crop["w"]), y=float(source_crop["y"])),
        Point2D(x=float(source_crop["x"] + source_crop["w"]), y=float(source_crop["y"] + source_crop["h"])),
        Point2D(x=float(source_crop["x"]), y=float(source_crop["y"] + source_crop["h"])),
    )
    destination_quad = tuple(_transform_point(matrix, corner) for corner in source_corners)
    destination_roi = _clamp_destination_roi(
        destination_quad,
        frame_width=int(feature.image_size.width),
        frame_height=int(feature.image_size.height),
    )
    if destination_roi is None:
        return None

    return RenderTask(
        source_crop=source_crop,
        destination_roi=destination_roi,
        destination_quad=destination_quad,
        matrix=matrix,
    )
