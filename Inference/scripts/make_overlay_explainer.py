from __future__ import annotations

import json
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.hairddae_runtime_manager import HairddaeRuntimeManager


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "mp_174417_preview.png"
OVERLAY_PATH = ROOT / "artifacts" / "mp_174417_preview_overlay_only_0013.png"
OUTPUT_PATH = ROOT / "artifacts" / "mp_174417_preview_overlay_only_0013_explained.png"
META_PATH = ROOT / "artifacts" / "mp_174417_preview_overlay_only_0013_explained.json"


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _pt(anchor: dict[str, float] | None) -> tuple[float, float] | None:
    if not isinstance(anchor, dict):
        return None
    x = anchor.get("x")
    y = anchor.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return float(x), float(y)


def _circle(draw: ImageDraw.ImageDraw, xy: tuple[float, float], r: int, fill: tuple[int, int, int, int], outline: tuple[int, int, int, int], width: int = 3) -> None:
    x, y = xy
    draw.ellipse((x - r, y - r, x + r, y + r), fill=fill, outline=outline, width=width)


def _arrow(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], fill: tuple[int, int, int, int], width: int = 4, head: int = 12) -> None:
    import math

    draw.line((start, end), fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    left = (
        end[0] - head * math.cos(angle - math.pi / 6),
        end[1] - head * math.sin(angle - math.pi / 6),
    )
    right = (
        end[0] - head * math.cos(angle + math.pi / 6),
        end[1] - head * math.sin(angle + math.pi / 6),
    )
    draw.polygon([end, left, right], fill=fill)


def main() -> None:
    settings = Settings.from_env()
    manager = HairddaeRuntimeManager(settings)
    try:
        frame_bgr = cv2.imread(str(INPUT_PATH), cv2.IMREAD_COLOR)
        if frame_bgr is None:
            raise RuntimeError(f"failed to load {INPUT_PATH}")
        result = manager.process_frame(
            dataset_code="0013",
            frame_bgr=frame_bgr,
            render_frame_bgr=frame_bgr,
            source_frame_bgr=frame_bgr,
            tracked_user_row=None,
            prefer_latency=False,
            session_id="overlay-explainer-0013",
            representative_asset_id=None,
            encode_output=False,
        )
    finally:
        manager.close()

    user_row = result.get("user_row") or {}
    anchors = user_row.get("anchors") or {}
    face_bbox = user_row.get("face_bbox") or {}
    if OVERLAY_PATH.is_file():
        base = Image.open(OVERLAY_PATH).convert("RGBA")
    else:
        output = result.get("output_frame_bgr")
        if output is None:
            raise RuntimeError("missing output frame")
        base = Image.fromarray(cv2.cvtColor(output, cv2.COLOR_BGR2RGBA))

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_title = _load_font(28)
    font_label = _load_font(20)
    font_small = _load_font(16)

    forehead_center = _pt(anchors.get("forehead_center"))
    crown = _pt(anchors.get("crown"))
    left_temple = _pt(anchors.get("left_temple"))
    right_temple = _pt(anchors.get("right_temple"))
    left_ear = _pt(anchors.get("left_ear_root"))
    right_ear = _pt(anchors.get("right_ear_root"))
    lower_left = _pt(anchors.get("lower_left"))
    lower_right = _pt(anchors.get("lower_right"))

    face_x = float(face_bbox.get("x", 0))
    face_y = float(face_bbox.get("y", 0))
    face_w = float(face_bbox.get("w", base.size[0] * 0.5))
    face_h = float(face_bbox.get("h", base.size[1] * 0.45))
    face_center = (face_x + face_w * 0.5, face_y + face_h * 0.52)

    # Anchor fit polygon
    anchor_color = (28, 237, 255, 255)
    anchor_fill = (28, 237, 255, 48)
    anchor_path = [pt for pt in [left_ear, left_temple, forehead_center or crown, right_temple, right_ear] if pt is not None]
    if len(anchor_path) >= 3:
        draw.line(anchor_path, fill=anchor_color, width=5)
        for pt in anchor_path:
            _circle(draw, pt, 8, fill=(255, 255, 255, 220), outline=anchor_color, width=3)
        if left_ear and right_ear:
            brow_arc_box = (
                left_ear[0] + 20,
                face_center[1] + 35,
                right_ear[0] - 20,
                face_center[1] + 170,
            )
            draw.arc(brow_arc_box, start=200, end=340, fill=anchor_color, width=4)
        draw.text((36, 36), "Anchor Fit", fill=anchor_color, font=font_title)
        draw.text((36, 72), "forehead, temple, and ear anchors", fill=(70, 85, 95, 255), font=font_small)

    # Mesh warp / scale polygon
    mesh_color = (255, 172, 52, 255)
    mesh_fill = (255, 172, 52, 40)
    if all(pt is not None for pt in [left_temple, right_temple, crown, lower_left, lower_right]):
        top_y = min(crown[1] + 8, left_temple[1] - 42, right_temple[1] - 42)
        poly = [
            (left_temple[0] - 38, left_temple[1] - 22),
            (face_center[0] - face_w * 0.22, top_y + 24),
            (face_center[0], top_y),
            (face_center[0] + face_w * 0.22, top_y + 24),
            (right_temple[0] + 38, right_temple[1] - 18),
            (right_temple[0] + 12, lower_right[1] - 10),
            (face_center[0] + face_w * 0.14, lower_right[1] + 40),
            (face_center[0] - face_w * 0.14, lower_left[1] + 34),
            (left_temple[0] - 12, lower_left[1] - 8),
        ]
        draw.polygon(poly, outline=mesh_color, fill=mesh_fill)
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        for i in range(1, 8):
            x = xmin + (xmax - xmin) * i / 8.0
            draw.line((x, ymin + 18, x, ymax - 24), fill=(255, 255, 255, 160), width=2)
        for i in range(1, 6):
            y = ymin + (ymax - ymin) * i / 6.0
            draw.line((xmin + 20, y, xmax - 20, y), fill=(255, 255, 255, 130), width=2)
        _arrow(draw, (xmin - 24, ymin + 76), (xmin - 4, ymin + 50), mesh_color, width=4)
        _arrow(draw, (xmax + 24, ymin + 76), (xmax + 4, ymin + 50), mesh_color, width=4)
        _arrow(draw, (xmin + 18, ymax - 30), (xmin + 2, ymax + 12), mesh_color, width=4)
        _arrow(draw, (xmax - 18, ymax - 30), (xmax - 2, ymax + 12), mesh_color, width=4)
        draw.text((36, base.size[1] - 98), "Scale + Mesh Warp", fill=mesh_color, font=font_title)
        draw.text((36, base.size[1] - 62), "face width, crown height, and temple direction", fill=(70, 85, 95, 255), font=font_small)

    # Tilt / natural edge
    tilt_color = (71, 224, 135, 255)
    white = (245, 250, 252, 220)
    if all(pt is not None for pt in [left_temple, right_temple, crown, left_ear, right_ear]):
        arc_box = (
            left_temple[0] - 18,
            crown[1] - 10,
            right_temple[0] + 18,
            crown[1] + 110,
        )
        draw.arc(arc_box, start=190, end=350, fill=tilt_color, width=5)
        if crown is not None:
            draw.ellipse((crown[0] - 42, crown[1] + 8, crown[0] + 42, crown[1] + 92), outline=white, width=4)
        draw.arc((left_ear[0] - 44, left_ear[1] - 36, left_ear[0] + 30, left_ear[1] + 92), start=90, end=270, fill=tilt_color, width=5)
        draw.arc((right_ear[0] - 30, right_ear[1] - 36, right_ear[0] + 44, right_ear[1] + 92), start=-90, end=90, fill=tilt_color, width=5)
        draw.ellipse((left_ear[0] - 54, left_ear[1] - 14, left_ear[0] - 2, left_ear[1] + 58), outline=white, width=4)
        draw.ellipse((right_ear[0] + 2, right_ear[1] - 14, right_ear[0] + 54, right_ear[1] + 58), outline=white, width=4)
        draw.text((base.size[0] - 222, 36), "Tilt + Natural Edge", fill=tilt_color, font=font_title)
        draw.text((base.size[0] - 222, 72), "keep ears and forehead exposed", fill=(70, 85, 95, 255), font=font_small)

    explained = Image.alpha_composite(base, overlay).convert("RGB")
    explained.save(OUTPUT_PATH, format="PNG")

    meta = {
        "input": str(INPUT_PATH),
        "base_overlay": str(OVERLAY_PATH),
        "output": str(OUTPUT_PATH),
        "dataset_code": "0013",
        "selected_asset_id": result.get("selected_asset_id"),
        "selection_mode": result.get("selection_mode"),
        "latency_ms": result.get("latency_ms"),
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
