// lib/face/types.ts
import type { NormalizedLandmark } from "@mediapipe/tasks-vision";

export type PoseStatus = "none" | "front" | "left" | "right";

export type PoseAngles = { yaw: number; pitch: number; roll: number };

export type FaceFrame = {
  t: number; // performance.now()
  videoW: number;
  videoH: number;
  faceFound: boolean;
  landmarks: NormalizedLandmark[];
  pose: PoseAngles | null;
};