// components/FaceLandmarksView.tsx
import type { RefObject } from "react";
import AlignmentGuide from "./AlignmentGuide";
import type { PoseStatus } from "@/lib/face/types";
import type { TxPhase } from "@/hooks/post/useMockTransmitFlow";

export default function FaceLandmarksView({
  videoRef,
  canvasRef,
  status,
  inGuide,
  tx,
}: {
  videoRef: RefObject<HTMLVideoElement | null>;
  canvasRef: RefObject<HTMLCanvasElement | null>;
  status: PoseStatus;
  inGuide: boolean;
  tx?: {
    phase: TxPhase;
    message: string;
    leftSeen: boolean;
    rightSeen: boolean;
  };
}) {
  const phase = tx?.phase ?? "idle";

  return (
    <div className="grid place-items-center gap-3">
      <div className="relative w-[min(900px,95vw)]">
        <video
          ref={videoRef}
          playsInline
          muted
          className="h-auto w-full -scale-x-100"
        />
        <AlignmentGuide className="-scale-x-100" status={status} />
        <canvas
          ref={canvasRef}
          className="pointer-events-none absolute inset-0 h-full w-full -scale-x-100"
        />
      </div>

      <div className="text-sm font-semibold">
        {phase === "sending" && (
          <span className="text-amber-600">
            {tx?.message} (왼쪽/오른쪽을 한 번씩 보여주세요){" "}
            <span className="text-gray-500">
              [L:{tx?.leftSeen ? "OK" : "-"} / R:{tx?.rightSeen ? "OK" : "-"}]
            </span>
          </span>
        )}

        {phase === "done" && <span className="text-green-600">{tx?.message}</span>}

        {phase === "idle" && (
          <>
            {!inGuide && (
              <span className="text-gray-500">가이드 안에 얼굴을 맞춰주세요</span>
            )}
            {inGuide && status === "front" && (
              <span className="text-blue-500">정면 인식 성공 (3초 유지)</span>
            )}
            {inGuide && status === "right" && (
              <span className="text-blue-500">오른쪽 인식 성공</span>
            )}
            {inGuide && status === "left" && (
              <span className="text-blue-500">왼쪽 인식 성공</span>
            )}
            {inGuide && status === "none" && (
              <span className="text-gray-500">고개를 맞춰주세요</span>
            )}
          </>
        )}
      </div>
    </div>
  );
}