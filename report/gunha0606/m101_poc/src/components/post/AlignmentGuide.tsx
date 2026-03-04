import type { PoseStatus } from "@/lib/face/types";

type Props = {
  className?: string;
  status?: PoseStatus;
};

export default function AlignmentGuide({ className = "", status = "none" }: Props) {
  const FACE = { cx: 500, cy: 190, rx: 120, ry: 150 };
  const SHOULDERS = { y: 350, half: 250, tick: 26 };
  const BODY = { x: 250, y: 350, w: 500, h: 220 };
  const HANDLE = { w: 18, h: 70, r: 9 };

  const isOk = status === "front" || status === "left" || status === "right";
  const STROKE = isOk ? "rgba(0, 140, 255, 0.95)" : "rgba(255,255,255,0.9)";
  const HANDLE_FILL = STROKE;

  return (
    <svg
      viewBox="0 0 1000 562"
      className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}
      preserveAspectRatio="none"
    >
      <rect
        x={BODY.x}
        y={BODY.y}
        width={BODY.w}
        height={BODY.h}
        fill="none"
        stroke={STROKE}
        strokeWidth={20}
      />

      <ellipse
        cx={FACE.cx}
        cy={FACE.cy}
        rx={FACE.rx}
        ry={FACE.ry}
        fill="none"
        stroke={STROKE}
        strokeWidth={10}
        strokeDasharray="18 18"
      />

      <line
        x1={FACE.cx - SHOULDERS.half}
        y1={SHOULDERS.y}
        x2={FACE.cx + SHOULDERS.half}
        y2={SHOULDERS.y}
        stroke={STROKE}
        strokeWidth={10}
        strokeLinecap="round"
      />

      <rect
        x={FACE.cx - SHOULDERS.half - HANDLE.w / 2}
        y={SHOULDERS.y - HANDLE.h / 2}
        width={HANDLE.w}
        height={HANDLE.h}
        rx={HANDLE.r}
        fill={HANDLE_FILL}
      />
      <rect
        x={FACE.cx + SHOULDERS.half - HANDLE.w / 2}
        y={SHOULDERS.y - HANDLE.h / 2}
        width={HANDLE.w}
        height={HANDLE.h}
        rx={HANDLE.r}
        fill={HANDLE_FILL}
      />

      <line
        x1={FACE.cx - SHOULDERS.half}
        y1={SHOULDERS.y - SHOULDERS.tick}
        x2={FACE.cx - SHOULDERS.half}
        y2={SHOULDERS.y + SHOULDERS.tick}
        stroke={STROKE}
        strokeWidth={10}
        strokeLinecap="round"
      />
      <line
        x1={FACE.cx + SHOULDERS.half}
        y1={SHOULDERS.y - SHOULDERS.tick}
        x2={FACE.cx + SHOULDERS.half}
        y2={SHOULDERS.y + SHOULDERS.tick}
        stroke={STROKE}
        strokeWidth={10}
        strokeLinecap="round"
      />
    </svg>
  );
}