import { useMemo, useRef } from 'react'
import { useFaceLandmarker } from '@/hooks/Camera/useFaceLandmarker'
import { useFaceTrackingLoop } from '@/hooks/Camera/useFaceTrackingLoop'
import { useUserMedia } from '@/hooks/Camera/useUserMedia'
import FaceLandmarksView from './face-landmarks-view'

export default function FaceTrackingCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null)

  const modelPath = useMemo(
    () => `${import.meta.env.BASE_URL}models/face_landmarker.task`,
    [],
  )

  const wasmPath = useMemo(() => `${import.meta.env.BASE_URL}mediapipe`, [])

  const cam = useUserMedia({ videoRef })

  const mp = useFaceLandmarker({
    modelAssetPath: modelPath,
    wasmBaseUrl: wasmPath,
  })

  useFaceTrackingLoop({
    videoRef,
    canvasRef,
    landmarkerRef: mp.landmarkerRef,
    enabled: cam.ready && mp.ready,
    yawSign: 1,
  })

  return (
    <FaceLandmarksView
      stream={cam.stream}
      transport="rtc"
      videoRef={videoRef}
      canvasRef={canvasRef}
      overlayCanvasRef={overlayCanvasRef}
    />
  )
}
