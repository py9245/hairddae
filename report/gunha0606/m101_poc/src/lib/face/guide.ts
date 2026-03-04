// lib/face/guide.ts
import type { NormalizedLandmark } from "@mediapipe/tasks-vision";

const GUIDE_VIEW = { w: 1000, h: 562 };
const GUIDE_FACE = { cx: 500, cy: 190, rx: 120, ry: 150 };
const FACE_ANCHORS = [10, 1, 33, 263, 61, 291, 152] as const;

const STRICT = { shrink: 0.9, minInside: 6 };

function inEllipse(
  x: number,
  y: number,
  e: { cx: number; cy: number; rx: number; ry: number }
) {
  const dx = (x - e.cx) / e.rx;
  const dy = (y - e.cy) / e.ry;
  return dx * dx + dy * dy <= 1;
}

export function isFaceInsideGuide(landmarks: NormalizedLandmark[]) {
  const e = {
    cx: GUIDE_FACE.cx,
    cy: GUIDE_FACE.cy,
    rx: GUIDE_FACE.rx * STRICT.shrink,
    ry: GUIDE_FACE.ry * STRICT.shrink,
  };

  let inside = 0;

  for (const idx of FACE_ANCHORS) {
    const lm = landmarks[idx];
    if (!lm) continue;

    const gx = lm.x * GUIDE_VIEW.w;
    const gy = lm.y * GUIDE_VIEW.h;

    if (inEllipse(gx, gy, e)) inside++;
  }

  return inside >= STRICT.minInside;
}