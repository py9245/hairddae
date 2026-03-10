import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useEffect, useRef, useState } from 'react'
import { isFaceInsideGuide } from '@/lib/Camera/guide'
import { classifyPose } from '@/lib/Camera/pose'
import type { FaceFrame, PoseStatus } from '@/lib/Camera/types'
import { updateFrameRef } from '@/lib/Camera/frame'
import {
  drawLandmarksCover,
  drawRedPointsCover,
  syncCanvasSize,
} from '@/lib/Camera/drawLandmarks'
import {
  useFaceLandmarksLoop,
  type LandmarkerLike,
} from '@/hooks/Camera/useFaceLandmarkersLoop'
import { useFacePose } from '@/hooks/Camera/useFacePose'

export function useFaceTrackingLoop({
  videoRef,
  canvasRef,
  landmarkerRef,
  enabled,
  yawSign = 1,
  frameRef,
}: {
  videoRef: React.RefObject<HTMLVideoElement | null>
  canvasRef: React.RefObject<HTMLCanvasElement | null>
  landmarkerRef: React.RefObject<LandmarkerLike | null>
  enabled: boolean
  yawSign?: number
  frameRef?: React.RefObject<FaceFrame | null>
}) {
  const rafRef = useRef<number | null>(null)
  const lastUpdateRef = useRef(0)

  const [status, setStatus] = useState<PoseStatus>('none')
  const [inGuide, setInGuide] = useState(false)
  const [landmarksState, setLandmarksState] =
    useState<NormalizedLandmark[] | null>(null)

  const { result, landmarks } = useFaceLandmarksLoop({
    videoRef,
    landmarkerRef,
    enabled,
  })

  const { ftm, pose, poseNorm } = useFacePose({
    result,
    yawSign,
  })

  useEffect(() => {
    const video = videoRef.current
    const canvas = canvasRef.current

    if (!enabled || !video || !canvas) return

    const loop = () => {
      rafRef.current = requestAnimationFrame(loop)

      if (video.readyState < 2) return

      const videoW = video.videoWidth
      const videoH = video.videoHeight
      if (videoW <= 0 || videoH <= 0) return

      syncCanvasSize(canvas)

      const now = performance.now()

      updateFrameRef(frameRef, now, videoW, videoH, landmarks, pose)

      if (landmarks) {
        const guideOk = isFaceInsideGuide(landmarks)

        if (now - lastUpdateRef.current > 120) {
          setInGuide(guideOk)
          setStatus(guideOk && ftm && pose ? classifyPose(pose) : 'none')
          setLandmarksState(landmarks)
          lastUpdateRef.current = now
        }
      } else {
        if (now - lastUpdateRef.current > 200) {
          setInGuide(false)
          setStatus('none')
          setLandmarksState(null)
          lastUpdateRef.current = now
        }
      }

      drawLandmarksCover(canvas, landmarks ?? [], videoW, videoH)

      if (landmarks) {
        drawRedPointsCover(canvas, landmarks, [10], videoW, videoH)
      }
    }

    rafRef.current = requestAnimationFrame(loop)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
  }, [enabled, videoRef, canvasRef, landmarks, ftm, pose, frameRef])

  return { status, inGuide, poseNorm, landmarks: landmarksState }
}