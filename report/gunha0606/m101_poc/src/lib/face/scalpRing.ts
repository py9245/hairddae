// src/lib/face/scalpRing.ts
import type { NormalizedLandmark } from "@mediapipe/tasks-vision";
import { FACE_OVAL } from "./mpTopology";

/**
 * FACE_OVAL 중 "이마/관자" 쪽 상단부만 뽑아서
 * atan2로 정렬된 "링 순서 인덱스"를 반환
 */
export function makeUpperOvalRingIdxs(
  lms: NormalizedLandmark[],
  topKeepRatio = 0.55 // 0.45~0.65 튜닝
): number[] {
  const pts = FACE_OVAL.map((idx) => ({
    idx,
    x: lms[idx].x,
    y: lms[idx].y,
  }));

  // y가 작을수록 위쪽(상단)
  const sortedByY = [...pts].sort((a, b) => a.y - b.y);
  const keepN = Math.max(10, Math.floor(sortedByY.length * topKeepRatio));
  const upper = sortedByY.slice(0, keepN);

  // 중심
  const cx = upper.reduce((s, p) => s + p.x, 0) / upper.length;
  const cy = upper.reduce((s, p) => s + p.y, 0) / upper.length;

  // atan2 정렬 (원형 순서)
  upper.sort(
    (a, b) =>
      Math.atan2(a.y - cy, a.x - cx) - Math.atan2(b.y - cy, b.x - cx)
  );

  return upper.map((p) => p.idx);
}