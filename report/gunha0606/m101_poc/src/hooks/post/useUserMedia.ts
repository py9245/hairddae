// src/components/hooks/useUserMedia.ts
import { useEffect, useState } from "react";

type UseUserMediaArgs = {
  videoEl: HTMLVideoElement | null;
  constraints?: MediaStreamConstraints;
  enabled?: boolean;
};

export function useUserMedia({
  videoEl,
  constraints = {
    video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
    audio: false,
  },
  enabled = true,
}: UseUserMediaArgs) {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!enabled || !videoEl) return;

    let cancelled = false;
    let localStream: MediaStream | null = null;

    const start = async () => {
      try {
        const s = await navigator.mediaDevices.getUserMedia(constraints);
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }

        localStream = s;
        videoEl.srcObject = s;
        await videoEl.play();

        setStream(s);
        setReady(true);
      } catch (e) {
        setError(e);
      }
    };

    start();

    return () => {
      cancelled = true;
      setReady(false);

      const s = localStream ?? stream;
      if (s) s.getTracks().forEach((t) => t.stop());

      if (videoEl) videoEl.srcObject = null;

      setStream(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, videoEl]);

  return { stream, ready, error };
}