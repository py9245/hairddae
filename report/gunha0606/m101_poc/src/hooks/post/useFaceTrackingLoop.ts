// hooks/useFaceTrackingLoop.ts
import { useEffect, useRef, useState } from "react";
import type { NormalizedLandmark } from "@mediapipe/tasks-vision";
import { drawLandmarks } from "@/lib/face/draw";
import { isFaceInsideGuide } from "@/lib/face/guide";
import { classifyPose, getHeadPoseFromMatrix } from "@/lib/face/pose";
import type { FaceFrame, PoseStatus } from "@/lib/face/types";

type LandmarkerLike = {
  detectForVideo: (video: HTMLVideoElement, ts: number) => any;
};

const FRAME_INTERVAL = 1000 / 30;

function syncCanvasSize(video: HTMLVideoElement, canvas: HTMLCanvasElement) {
  if (canvas.width !== video.videoWidth) canvas.width = video.videoWidth;
  if (canvas.height !== video.videoHeight) canvas.height = video.videoHeight;
}

function updateFrameRef(
  frameRef: React.RefObject<FaceFrame | null> | undefined,
  now: number,
  w: number,
  h: number,
  lms: NormalizedLandmark[] | null,
  pose: FaceFrame["pose"]
) {
  if (!frameRef) return;
  frameRef.current = {
    t: now,
    videoW: w,
    videoH: h,
    faceFound: !!lms,
    landmarks: lms ?? [],
    pose,
  };
}

export function useFaceTrackingLoop({
  videoRef,
  canvasRef,
  landmarkerRef,
  enabled,
  yawSign = 1,

  frameRef,
}: {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  landmarkerRef: React.RefObject<LandmarkerLike | null>;
  enabled: boolean;
  yawSign?: number;

  frameRef?: React.RefObject<FaceFrame | null>;
}) {
  const rafRef = useRef<number | null>(null);
  const lastDetectRef = useRef(0);
  const lastUpdateRef = useRef(0);

  const [status, setStatus] = useState<PoseStatus>("none");
  const [inGuide, setInGuide] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const landmarker = landmarkerRef.current;

    if (!enabled || !video || !canvas || !landmarker) return;

    const loop = () => {
      rafRef.current = requestAnimationFrame(loop);

      if (video.readyState < 2) return;

      const w = video.videoWidth;
      const h = video.videoHeight;
      if (w <= 0 || h <= 0) return;

      const now = performance.now();
      if (now - lastDetectRef.current < FRAME_INTERVAL) return;
      lastDetectRef.current = now;

      syncCanvasSize(video, canvas);

      const res = landmarker.detectForVideo(video, now);
      const lms = (res.faceLandmarks?.[0] ?? null) as NormalizedLandmark[] | null;

      const ftm = res.facialTransformationMatrixes?.[0]?.data;
      const pose = ftm ? getHeadPoseFromMatrix(ftm, yawSign) : null;

      updateFrameRef(frameRef, now, w, h, lms, pose);

      if (lms) {
        const guideOk = isFaceInsideGuide(lms);
        if (now - lastUpdateRef.current > 120) {
          setInGuide(guideOk);
          setStatus(guideOk && ftm && pose ? classifyPose(pose) : "none");
          lastUpdateRef.current = now;
        }
      } else {
        if (now - lastUpdateRef.current > 200) {
          setInGuide(false);
          setStatus("none");
          lastUpdateRef.current = now;
        }
      }

      drawLandmarks(canvas, lms ?? []);
    };

    rafRef.current = requestAnimationFrame(loop);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [enabled, yawSign, videoRef, canvasRef, landmarkerRef, frameRef]);

  return { status, inGuide };
}