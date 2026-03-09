import { useMemo, useRef } from 'react'
import FaceLandmarksView from '@/components/Camera/FaceLandmarksView'
import { useFaceLandmarker } from '@/hooks/Camera/useFaceLandmarker'
import { useFaceTrackingLoop } from '@/hooks/Camera/useFaceTrackingLoop'
import { useUserMedia } from '@/hooks/Camera/useUserMedia'

export default function Camera() {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  const modelPath = useMemo(
    () => `${import.meta.env.BASE_URL}models/face_landmarker.task`,
    [],
  )

  const cam = useUserMedia({ videoRef })

  const mp = useFaceLandmarker({
    modelAssetPath: modelPath,
    wasmBaseUrl:
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm',
  })

  const { poseNorm, landmarks } = useFaceTrackingLoop({
    videoRef,
    canvasRef,
    landmarkerRef: mp.landmarkerRef,
    enabled: cam.ready && mp.ready,
    yawSign: 1,
  })

  return (
    <FaceLandmarksView
      videoRef={videoRef}
      canvasRef={canvasRef}
      poseNorm={poseNorm}
      landmarks={landmarks}
    />
  )
}
