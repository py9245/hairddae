// components/FaceLandmarks.tsx
import { useMemo, useRef } from "react";
import { useUserMedia } from "@/hooks/post/useUserMedia";
import { useFaceLandmarker } from "@/hooks/post/useFaceLandmarker";
import { useFaceTrackingLoopBald } from "@/hooks/bald/useFaceTrackingLoopBald";
import FaceLandmarksViewBald from "@/components/bald/FaceLandmarksViewBald";

export default function FaceLandmarks() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const threeCanvasRef = useRef<HTMLCanvasElement | null>(null); // ✅ 추가

  const modelPath = useMemo(
    () => `${import.meta.env.BASE_URL}models/face_landmarker.task`,
    []
  );

  const cam = useUserMedia({ videoEl: videoRef.current });

  const mp = useFaceLandmarker({
    modelAssetPath: modelPath,
    wasmBaseUrl: "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm",
  });

  useFaceTrackingLoopBald({
    videoRef,
    canvasRef,
    threeCanvasRef, // ✅ 추가
    landmarkerRef: mp.landmarkerRef,
    enabled: cam.ready && mp.ready,
    yawSign: 1,
  });

  return (
    <FaceLandmarksViewBald
      videoRef={videoRef}
      canvasRef={canvasRef}
      threeCanvasRef={threeCanvasRef} // ✅ 추가
    />
  );
}