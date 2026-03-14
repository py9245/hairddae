import { useEffect, useMemo, useRef, useState } from 'react'
import FaceLandmarksView from '@/components/Camera/FaceLandmarksView'
import { useFaceLandmarker } from '@/hooks/Camera/useFaceLandmarker'
import { useFaceTrackingLoop } from '@/hooks/Camera/useFaceTrackingLoop'
import { useHairRecommendFlow } from '@/hooks/Camera/useHairRecommendFlow'
import { useUserMedia } from '@/hooks/Camera/useUserMedia'
import type { FaceFrame } from '@/lib/Camera/types'

export default function Camera() {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const frameRef = useRef<FaceFrame | null>(null)
  const [hairID, setHairID] = useState(0)

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

  const { pose, landmarks } = useFaceTrackingLoop({
    videoRef,
    canvasRef,
    landmarkerRef: mp.landmarkerRef,
    enabled: cam.ready && mp.ready,
    yawSign: 1,
    frameRef,
  })

  const flow = useHairRecommendFlow()
  const { clearRecommendation, requestByPose } = flow

  useEffect(() => {
    if (hairID <= 0) {
      clearRecommendation()
      return
    }

    if (!cam.ready || !pose) {
      return
    }

    void requestByPose(hairID, pose).catch(() => {})
  }, [cam.ready, clearRecommendation, hairID, landmarks, pose, requestByPose])

  return (
    <FaceLandmarksView
      videoRef={videoRef}
      canvasRef={canvasRef}
      overlayCanvasRef={overlayCanvasRef}
      landmarks={landmarks}
      frameRef={frameRef}
      selectedHairId={hairID}
      onHairApplied={setHairID}
      recommendation={flow.recommendation}
      overlayImage={flow.overlayImage}
      activeAsset={flow.activeAsset}
      loading={flow.loading}
      error={flow.error}
    />
  )
}
