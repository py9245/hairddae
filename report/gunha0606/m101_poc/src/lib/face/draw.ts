// lib/face/draw.ts
import type { NormalizedLandmark } from "@mediapipe/tasks-vision";

export function drawLandmarks(
  canvas: HTMLCanvasElement,
  landmarks: NormalizedLandmark[]
) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "rgba(0, 255, 0, 0.9)";
  const r = 2;

  ctx.beginPath();
  for (const p of landmarks) {
    const x = p.x * canvas.width;
    const y = p.y * canvas.height;
    ctx.moveTo(x + r, y);
    ctx.arc(x, y, r, 0, Math.PI * 2);
  }
  ctx.fill();
}