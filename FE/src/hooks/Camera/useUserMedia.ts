import { useEffect, useState } from 'react'

type UseUserMediaArgs = {
  videoRef: React.RefObject<HTMLVideoElement | null>
  constraints?: MediaStreamConstraints
  enabled?: boolean
}

const DEFAULT_CONSTRAINTS: MediaStreamConstraints = {
  video: {
    facingMode: 'user',
    width: { ideal: 1280 },
    height: { ideal: 720 },
  },
  audio: false,
}

export function useUserMedia({
  videoRef,
  constraints = DEFAULT_CONSTRAINTS,
  enabled = true,
}: UseUserMediaArgs) {
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    const videoEl = videoRef.current
    if (!enabled || !videoEl) return

    let cancelled = false
    let localStream: MediaStream | null = null

    const start = async () => {
      try {
        const s = await navigator.mediaDevices.getUserMedia(constraints)

        if (cancelled) {
          s.getTracks().forEach((t) => {
            t.stop()
          })
          return
        }

        localStream = s
        videoEl.srcObject = s
        await videoEl.play()

        setStream(s)
        setReady(true)
        setError(null)
      } catch (e) {
        setError(e)
        setReady(false)
      }
    }

    void start()

    return () => {
      cancelled = true
      setReady(false)

      if (localStream) {
        localStream.getTracks().forEach((t) => {
          t.stop()
        })
      }

      videoEl.srcObject = null
      setStream(null)
    }
  }, [videoRef, enabled, constraints])

  return { stream, ready, error }
}
