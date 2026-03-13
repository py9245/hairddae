import { useEffect, useMemo, useRef, useState } from 'react'
import FaceLandmarksView from '@/components/Camera/FaceLandmarksView'
import { useFaceLandmarker } from '@/hooks/Camera/useFaceLandmarker'
import { useFaceTrackingLoop } from '@/hooks/Camera/useFaceTrackingLoop'
import { useHairRecommendFlow } from '@/hooks/Camera/useHairRecommendFlow'
import { useUserMedia } from '@/hooks/Camera/useUserMedia'

export default function Camera() {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const frameIdRef = useRef(0)
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
  })

  const flow = useHairRecommendFlow()
  const { buildFeatureMessage, clearRecommendation, requestByPose } = flow

useEffect(() => {
  if (!landmarks || landmarks.length === 0 || !pose) {
    return
  }

  const video = videoRef.current
  if (!video || !cam.ready || hairID <= 0) {
    return
  }

  frameIdRef.current += 1

  try {
    const message = buildFeatureMessage({
      hairID,
      videoWidth: video.videoWidth,
      videoHeight: video.videoHeight,
      landmarks,
      pose,
      userId: 'user-123',
      frameId: frameIdRef.current,
      requestId: `camera-${hairID}-${frameIdRef.current}`,
    })

    console.log('feature message:', message)
  } catch (error) {
    console.error('buildFeatureMessage 실패', {
      error,
      hairID,
      videoWidth: video.videoWidth,
      videoHeight: video.videoHeight,
      pose,
      landmarksCount: landmarks.length,
      frameId: frameIdRef.current,
    })
  }
}, [buildFeatureMessage, cam.ready, hairID, landmarks, pose])

useEffect(() => {
    if (hairID <= 0) {
      clearRecommendation()
      return
    }

    if (!cam.ready || !landmarks || landmarks.length === 0 || !pose) {
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
      selectedHairId={hairID}
      onHairApplied={setHairID}
      recommendation={flow.recommendation}
      overlayImage={flow.overlayImage}
      loading={flow.loading}
      error={flow.error}
    />
  )
}
