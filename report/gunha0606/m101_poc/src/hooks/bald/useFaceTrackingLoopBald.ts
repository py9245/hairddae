import { useEffect, useRef } from "react";
import type { FaceFrame } from "@/lib/face/types";

import { createBaldThree } from "@/hooks/bald/createBaldThree";
import { initHairSegmenter, getHairSegmenter } from "@/lib/segmentation/hairSegmenter";


type LandmarkerLike = {
  detectForVideo: (video: HTMLVideoElement, ts: number) => any;
};

const FRAME_INTERVAL = 1000 / 30;
const SEG_INTERVAL = 1000 / 12;

function syncCanvasSize(video: HTMLVideoElement, canvas: HTMLCanvasElement) {
  if (canvas.width !== video.videoWidth) canvas.width = video.videoWidth;
  if (canvas.height !== video.videoHeight) canvas.height = video.videoHeight;
}

export function useFaceTrackingLoopBald({
  videoRef,
  canvasRef,
  threeCanvasRef,
  landmarkerRef,
  enabled,
  yawSign = 1,
  frameRef,
}: {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  threeCanvasRef: React.RefObject<HTMLCanvasElement | null>;
  landmarkerRef: React.RefObject<LandmarkerLike | null>;
  enabled: boolean;
  yawSign?: number;
  frameRef?: React.RefObject<FaceFrame | null>;
}) {
  const rafRef = useRef<number | null>(null);
  const lastDetectRef = useRef(0);
  const lastSegRef = useRef(0);


  const baldThreeRef = useRef<ReturnType<typeof createBaldThree> | null>(null);
  const segInitOnceRef = useRef(false);

  useEffect(() => {
    const video = videoRef.current;
    const canvas2D = canvasRef.current;
    const canvas3D = threeCanvasRef.current;
    const landmarker = landmarkerRef.current;

    if (!enabled || !video || !canvas2D || !canvas3D || !landmarker) return;

    if (!segInitOnceRef.current) {
      segInitOnceRef.current = true;
      void initHairSegmenter();
    }

    if (!baldThreeRef.current) {
      baldThreeRef.current = createBaldThree(canvas3D);
    }

    const loop = () => {
      rafRef.current = requestAnimationFrame(loop);

      if (video.readyState < 2) return;

      const w = video.videoWidth;
      const h = video.videoHeight;
      if (w <= 0 || h <= 0) return;

      const now = performance.now();
      if (now - lastDetectRef.current < FRAME_INTERVAL) return;
      lastDetectRef.current = now;

      syncCanvasSize(video, canvas2D);
      baldThreeRef.current?.resize(w, h);

      // 3) Hair segmentation 먼저 (throttle)
      const seg = getHairSegmenter();
      if (seg && now - lastSegRef.current > SEG_INTERVAL) {
        lastSegRef.current = now;
        try {
          const segRes: any = seg.segmentForVideo(video, now);
          const cm = segRes?.categoryMask;

          if (cm) {
            const mw = cm.width as number;
            const mh = cm.height as number;

            const raw: Uint8Array | Float32Array =
              typeof cm.getAsUint8Array === "function"
                ? (cm.getAsUint8Array() as Uint8Array)
                : (cm.getAsFloat32Array?.() as Float32Array);

            if (raw && mw > 0 && mh > 0) {
              const mask01 = new Uint8ClampedArray(mw * mh);
              if (raw instanceof Uint8Array) {
                for (let i = 0; i < mw * mh; i++) mask01[i] = raw[i] > 0 ? 1 : 0;
              } else {
                for (let i = 0; i < mw * mh; i++) mask01[i] = raw[i] > 0.5 ? 1 : 0;
              }
              baldThreeRef.current?.updateHairMask(mask01, mw, mh);
            }
          }
        } catch {
          // ignore
        }
      }

      // 4) 2D 디버그 렌더 (video는 video 태그가 보여주는 전제)
      const ctx = canvas2D.getContext("2d");
      if (!ctx) return;

      ctx.clearRect(0, 0, w, h);
      baldThreeRef.current?.debugDrawHairMaskTo(ctx, w, h);


    };

    rafRef.current = requestAnimationFrame(loop);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;

      baldThreeRef.current?.dispose();
      baldThreeRef.current = null;
    };
  }, [enabled, yawSign, videoRef, canvasRef, threeCanvasRef, landmarkerRef, frameRef]);

  return { status, };
}