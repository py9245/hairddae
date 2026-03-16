import type { RefObject, ReactNode } from 'react'
import { useMemo, useRef } from 'react'
import { useFaceLandmarker } from '@/hooks/Camera/useFaceLandmarker'
import { useFaceTrackingLoop } from '@/hooks/Camera/useFaceTrackingLoop'
import { useUserMedia } from '@/hooks/Camera/useUserMedia'

type LandmarkPoint = {
  x: number
  y: number
  z: number
}

type Pose = {
  yaw: number
  pitch: number
  roll: number
}

type FaceExportRenderProps = {
  videoRef: RefObject<HTMLVideoElement | null>
  canvasRef: RefObject<HTMLCanvasElement | null>
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>
  landmarks: LandmarkPoint[] | null
  pose: Pose | null
}

type FaceExportProps = {
  children: (props: FaceExportRenderProps) => ReactNode
}

export default function FaceExport({ children }: FaceExportProps) {
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

  const { pose, landmarks } = useFaceTrackingLoop({
    videoRef,
    canvasRef,
    landmarkerRef: mp.landmarkerRef,
    enabled: cam.ready && mp.ready,
    yawSign: 1,
  })

  return children({
    videoRef,
    canvasRef,
    overlayCanvasRef,
    landmarks,
    pose,
  })
}
