// components/FaceLandmarksViewBald.tsx
import type { RefObject } from "react";

export default function FaceLandmarksViewBald({
  videoRef,
  canvasRef,
  threeCanvasRef,
}: {
  videoRef: RefObject<HTMLVideoElement | null>;
  canvasRef: RefObject<HTMLCanvasElement | null>;
  threeCanvasRef: RefObject<HTMLCanvasElement | null>;
}) {
  return (
    <div className="grid place-items-center">
      <div className="relative w-[min(900px,95vw)]">
        <video
          ref={videoRef}
          playsInline
          muted
          className="h-auto w-full -scale-x-100"
        />

        {/* ✅ Three.js WebGL 캔버스 (두피 돔) */}
        <canvas
          ref={threeCanvasRef}
          className="pointer-events-none absolute inset-0 h-full w-full -scale-x-100"
        />

        {/* ✅ 2D 디버그(랜드마크) */}
        <canvas
          ref={canvasRef}
          className="pointer-events-none absolute inset-0 h-full w-full -scale-x-100"
        />
      </div>
    </div>
  );
}