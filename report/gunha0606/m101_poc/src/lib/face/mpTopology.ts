// src/lib/face/mpTopology.ts
import { FACEMESH_FACE_OVAL } from "@mediapipe/face_mesh";

/**
 * @mediapipe/face_mesh 의 FACEMESH_FACE_OVAL 은
 * (startIdx, endIdx) 형태의 pair 리스트로 제공됨.
 * 우리는 "점 인덱스 리스트"가 필요하므로 flatten + unique 처리.
 */
export const FACE_OVAL: number[] = Array.from(
  new Set(FACEMESH_FACE_OVAL.flat())
);