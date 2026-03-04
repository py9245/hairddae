// components/FaceLandmarks.tsx
import { useMemo, useRef } from "react";
import { useUserMedia } from "@/hooks/post/useUserMedia";
import { useFaceLandmarker } from "@/hooks/post/useFaceLandmarker";
import { useFaceTrackingLoop } from "@/hooks/post/useFaceTrackingLoop";
import { useMockTransmitFlow } from "@/hooks/post/useMockTransmitFlow";
import FaceLandmarksView from "@/components/post/FaceLandmarksView";
import type { FaceFrame } from "@/lib/face/types";

export default function FaceLandmarks() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const frameRef = useRef<FaceFrame | null>(null);

  const modelPath = useMemo(
    () => `${import.meta.env.BASE_URL}models/face_landmarker.task`,
    []
  );

  const cam = useUserMedia({ videoEl: videoRef.current });

  const mp = useFaceLandmarker({
    modelAssetPath: modelPath,
    wasmBaseUrl: "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm",
  });

  const { status, inGuide } = useFaceTrackingLoop({
    videoRef,
    canvasRef,
    landmarkerRef: mp.landmarkerRef,
    enabled: cam.ready && mp.ready,
    yawSign: 1,

    frameRef,
  });

const tx = useMockTransmitFlow({
  userId: "test-user-001", // TODO: 나중에 실제 로그인/세션 값
  status,
  inGuide,
  frameRef,
  autoDownloadOnDone: true,
});

  return (
    <FaceLandmarksView
      videoRef={videoRef}
      canvasRef={canvasRef}
      status={status}
      inGuide={inGuide}
      tx={tx}
    />
  );
}