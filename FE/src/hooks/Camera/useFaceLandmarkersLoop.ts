import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useEffect, useRef, useState } from 'react'
import { CAMERA_FRAME_INTERVAL_MS } from '@/lib/Camera/runtime'

export type DetectForVideoResult = {
  faceLandmarks?: NormalizedLandmark[][]
  facialTransformationMatrixes?: Array<{
    data?: number[] | Float32Array
  }>
}

export type LandmarkerLike = {
  detectForVideo: (video: HTMLVideoElement, ts: number) => DetectForVideoResult
}

const FRAME_INTERVAL_MS = CAMERA_FRAME_INTERVAL_MS

export function useFaceLandmarksLoop({
  videoRef,
  landmarkerRef,
  enabled,
  publishState = true,
}: {
  videoRef: React.RefObject<HTMLVideoElement | null>
  landmarkerRef: React.RefObject<LandmarkerLike | null>
  enabled: boolean
  publishState?: boolean
}) {
  const rafRef = useRef<number | null>(null)
  const lastDetectRef = useRef(0)
  const resultRef = useRef<DetectForVideoResult | null>(null)
  const landmarksRef = useRef<NormalizedLandmark[] | null>(null)

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
      if (now - lastDetectRef.current < FRAME_INTERVAL_MS) return
      lastDetectRef.current = now

      const res = landmarker.detectForVideo(video, now)
      const nextLandmarks = res.faceLandmarks?.[0] ?? null
      resultRef.current = res
      landmarksRef.current = nextLandmarks

      if (publishState) {
        setResult(res)
        setLandmarks(nextLandmarks)
      }
    }

    rafRef.current = requestAnimationFrame(loop)

    return () => {
      active = false
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
      }
      rafRef.current = null
    }
  }, [enabled, landmarkerRef, publishState, videoRef])

  return { result, landmarks, resultRef, landmarksRef }
}
