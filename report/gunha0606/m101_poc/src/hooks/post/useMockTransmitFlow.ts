import { useEffect, useRef, useState } from "react";
import type { FaceFrame, PoseStatus } from "@/lib/face/types";
import { downloadJsonFile } from "@/lib/face/downloadJson";

export type TxPhase = "idle" | "sending" | "done";

export function useMockTransmitFlow({
  userId,
  status,
  inGuide,
  frameRef,
  autoDownloadOnDone = true,

  // ✅ 옵션
  angleStepDeg = 1,          // 1이면 1도 단위, 5면 5도 단위로 양자화
  overwriteIfExists = false, // 같은 key가 또 나오면 덮어쓸지
  pickAllLandmarks = true,   // true면 모든 landmarks 저장, false면 원하는 인덱스만 저장
  pickLmIdxs = [],           // pickAllLandmarks=false일 때만 사용
}: {
  userId: string;
  status: PoseStatus;
  inGuide: boolean;
  frameRef: React.RefObject<FaceFrame | null>;
  autoDownloadOnDone?: boolean;

  angleStepDeg?: number;
  overwriteIfExists?: boolean;
  pickAllLandmarks?: boolean;
  pickLmIdxs?: number[];
}) {
  const [phase, setPhase] = useState<TxPhase>("idle");

  const frontSinceRef = useRef<number | null>(null);
  const leftSeenRef = useRef(false);
  const rightSeenRef = useRef(false);

  // ✅ 최종 로그(JSON)
  const logRef = useRef<Record<string, any>>({});

  // ✅ RAF
  const rafIdRef = useRef<number | null>(null);

  const downloadLog = () => {
    const filename = `face_angles_${userId}_${new Date()
      .toISOString()
      .replaceAll(":", "-")}.json`;
    downloadJsonFile(logRef.current, filename);
  };

  // 0~359 정규화 + step 적용
  const quantize = (deg: number) => {
    const stepped = Math.round(deg / angleStepDeg) * angleStepDeg;
    const v = ((stepped % 360) + 360) % 360;
    return v; // 0..359 (step 적용 시 0..359 중 일부만)
  };

  const makeKey = (x: number, y: number, z: number) => {
    return x * 360 * 360 + y * 360 + z; // number
  };

  // 1) 정면 3초 유지 → sending 시작
  useEffect(() => {
    if (phase !== "idle") return;

    const timer = window.setInterval(() => {
      const now = performance.now();

      if (inGuide && status === "front") {
        if (frontSinceRef.current == null) frontSinceRef.current = now;

        if (now - frontSinceRef.current >= 3000) {
          setPhase("sending");
          leftSeenRef.current = false;
          rightSeenRef.current = false;

          // ✅ 네가 원하는 최상위 구조 시작
          logRef.current = {
            [userId]: {}, // <- 여기에 key: landmarks가 쌓임
            startedAtTs: Date.now(),
            config: { angleStepDeg, overwriteIfExists, pickAllLandmarks, pickLmIdxs },
          };
        }
      } else {
        frontSinceRef.current = null;
      }
    }, 100);

    return () => window.clearInterval(timer);
  }, [phase, inGuide, status, userId, angleStepDeg, overwriteIfExists, pickAllLandmarks, pickLmIdxs]);

  // 2) sending 중 좌/우 1번씩 인식 → done
  useEffect(() => {
    if (phase !== "sending") return;

    if (inGuide && status === "left") leftSeenRef.current = true;
    if (inGuide && status === "right") rightSeenRef.current = true;

    if (leftSeenRef.current && rightSeenRef.current) setPhase("done");
  }, [phase, status, inGuide]);

  // 3) ✅ 프레임마다 (x,y,z)각도 -> key 생성 -> landmarks 저장
  useEffect(() => {
    if (phase !== "sending") return;

    const tick = () => {
      const f = frameRef.current;

      // ✅ pose null 가능성 처리
      if (f && f.faceFound && inGuide && f.pose) {
        // 여기서 x,y,z는 "각도"로 가정: x=pitch, y=yaw, z=roll
        const x = quantize(f.pose.pitch);
        const y = quantize(f.pose.yaw);
        const z = quantize(f.pose.roll);

        const k = String(makeKey(x, y, z));

        const userMap = logRef.current[userId] as Record<string, any>;

        const exists = userMap[k] != null;
        if (!exists || overwriteIfExists) {
          const pts = pickAllLandmarks
            ? f.landmarks.map((p) => [p.x, p.y, p.z])
            : pickLmIdxs.map((i) => {
                const p = f.landmarks[i];
                return [p.x, p.y, p.z];
              });

          // ✅ 네가 말한 형식: key -> ["랜드마크 좌표들]
          // (실제로는 number[][]가 자연스러움)
          userMap[k] = pts;
        }
      }

      rafIdRef.current = requestAnimationFrame(tick);
    };

    rafIdRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    };
  }, [phase, frameRef, inGuide, userId, angleStepDeg, overwriteIfExists, pickAllLandmarks, pickLmIdxs]);

  // 4) done 시 다운로드
  useEffect(() => {
    if (phase !== "done") return;

    if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    rafIdRef.current = null;

    logRef.current.endedAtTs = Date.now();
    logRef.current.progress = {
      leftSeen: leftSeenRef.current,
      rightSeen: rightSeenRef.current,
      keys: Object.keys(logRef.current[userId] ?? {}).length,
    };

    if (autoDownloadOnDone) downloadLog();
  }, [phase, autoDownloadOnDone, userId]);

  return {
    phase,
    message:
      phase === "sending"
        ? `각도 key 수집중... (keys=${Object.keys(logRef.current[userId] ?? {}).length})`
        : phase === "done"
        ? "전송 완료"
        : "",
    leftSeen: leftSeenRef.current,
    rightSeen: rightSeenRef.current,
    downloadLog,
  };
}