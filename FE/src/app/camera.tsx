import { useMemo, useRef } from 'react'
import FaceLandmarksView from '@/components/Camera/face-landmarks-view'
import { useFaceLandmarker } from '@/hooks/Camera/useFaceLandmarker'
import { useFaceTrackingLoop } from '@/hooks/Camera/useFaceTrackingLoop'
import { useUserMedia } from '@/hooks/Camera/useUserMedia'
import {
  HAIR_TRANSPORT,
  RTC_CAPTURE_FPS,
  RTC_CAPTURE_HEIGHT,
  RTC_CAPTURE_WIDTH,
} from '@/lib/Camera/runtime'
import type { FaceFrame } from '@/lib/Camera/types'

export default function Camera() {
  const sourceVideoRef = useRef<HTMLVideoElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const faceFrameRef = useRef<FaceFrame | null>(null)

  const modelPath = useMemo(
    () => `${import.meta.env.BASE_URL}models/face_landmarker.task`,
    [],
  )

  const wasmPath = useMemo(() => `${import.meta.env.BASE_URL}mediapipe`, [])
  const mediaConstraints = useMemo<MediaStreamConstraints | undefined>(() => {
    if (HAIR_TRANSPORT !== 'rtc') {
      return undefined
    }

    return {
      video: {
        facingMode: 'user',
        width: { ideal: RTC_CAPTURE_WIDTH, max: RTC_CAPTURE_WIDTH },
        height: { ideal: RTC_CAPTURE_HEIGHT, max: RTC_CAPTURE_HEIGHT },
        frameRate: { ideal: RTC_CAPTURE_FPS, max: RTC_CAPTURE_FPS },
      },
      audio: false,
    }
  }, [])

  const cam = useUserMedia({ videoRef: sourceVideoRef, constraints: mediaConstraints })
  const shouldUseClientTracking = HAIR_TRANSPORT !== 'rtc'

  const mp = useFaceLandmarker({
    enabled: shouldUseClientTracking,
    modelAssetPath: modelPath,
    wasmBaseUrl: wasmPath,
  })

  useFaceTrackingLoop({
    videoRef,
    canvasRef,
    landmarkerRef: mp.landmarkerRef,
    enabled: shouldUseClientTracking && cam.ready && mp.ready,
    yawSign: 1,
    frameRef: faceFrameRef,
    drawDebugOverlay: shouldUseClientTracking,
    publishState: shouldUseClientTracking,
  })

  return (
    <FaceLandmarksView
      sourceVideoRef={sourceVideoRef}
      stream={cam.stream}
      transport={HAIR_TRANSPORT}
      videoRef={videoRef}
      canvasRef={canvasRef}
      overlayCanvasRef={overlayCanvasRef}
    />
  )
}
