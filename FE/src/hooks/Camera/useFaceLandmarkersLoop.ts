import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useEffect, useRef, useState } from 'react'

export type DetectForVideoResult = {
  faceLandmarks?: NormalizedLandmark[][]
  facialTransformationMatrixes?: Array<{
    data?: number[] | Float32Array
  }>
}

export type LandmarkerLike = {
  detectForVideo: (video: HTMLVideoElement, ts: number) => DetectForVideoResult
}

const FRAME_INTERVAL = 1000 / 30

export function useFaceLandmarksLoop({
  videoRef,
  landmarkerRef,
  enabled,
}: {
  videoRef: React.RefObject<HTMLVideoElement | null>
  landmarkerRef: React.RefObject<LandmarkerLike | null>
  enabled: boolean
}) {
  const rafRef = useRef<number | null>(null)
  const lastDetectRef = useRef(0)

  const [result, setResult] = useState<DetectForVideoResult | null>(null)
  const [landmarks, setLandmarks] = useState<NormalizedLandmark[] | null>(null)

  useEffect(() => {
    let active = true

    const loop = () => {
      if (!active) return

      rafRef.current = requestAnimationFrame(loop)

      const video = videoRef.current
      const landmarker = landmarkerRef.current

      if (!enabled || !video || !landmarker) return
      if (video.readyState < 2) return
      if (video.videoWidth <= 0 || video.videoHeight <= 0) return

      const now = performance.now()
      if (now - lastDetectRef.current < FRAME_INTERVAL) return
      lastDetectRef.current = now

      const res = landmarker.detectForVideo(video, now)
      const nextLandmarks = res.faceLandmarks?.[0] ?? null

      setResult(res)
      setLandmarks(nextLandmarks)
    }

    rafRef.current = requestAnimationFrame(loop)

    return () => {
      active = false
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
      }
      rafRef.current = null
    }
  }, [enabled, videoRef, landmarkerRef])

  return { result, landmarks }
}
