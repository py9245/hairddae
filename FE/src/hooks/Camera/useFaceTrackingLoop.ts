import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useEffect, useRef, useState } from 'react'
import {
  type LandmarkerLike,
  useFaceLandmarksLoop,
} from '@/hooks/Camera/useFaceLandmarkersLoop'
import { deriveFacePose, useFacePose } from '@/hooks/Camera/useFacePose'
import {
  drawLandmarksCover,
  drawRedPointsCover,
  syncCanvasSize,
} from '@/lib/Camera/drawLandmarks'
import { updateFrameRef } from '@/lib/Camera/frame'
import { isFaceInsideGuide } from '@/lib/Camera/guide'
import { classifyPose } from '@/lib/Camera/pose'
import { CAMERA_FRAME_INTERVAL_MS } from '@/lib/Camera/runtime'
import type { FaceFrame, PoseStatus } from '@/lib/Camera/types'

const FRAME_INTERVAL_MS = CAMERA_FRAME_INTERVAL_MS
const LOST_FACE_RESET_MS = FRAME_INTERVAL_MS * 2

export function useFaceTrackingLoop({
  videoRef,
  canvasRef,
  landmarkerRef,
  enabled,
  yawSign = 1,
  frameRef,
  drawDebugOverlay = true,
  publishState = true,
}: {
  videoRef: React.RefObject<HTMLVideoElement | null>
  canvasRef: React.RefObject<HTMLCanvasElement | null>
  landmarkerRef: React.RefObject<LandmarkerLike | null>
  enabled: boolean
  yawSign?: number
  frameRef?: React.RefObject<FaceFrame | null>
  drawDebugOverlay?: boolean
  publishState?: boolean
}) {
  const rafRef = useRef<number | null>(null)
  const lastUpdateRef = useRef(0)

  const [status, setStatus] = useState<PoseStatus>('none')
  const [inGuide, setInGuide] = useState(false)
  const [landmarksState, setLandmarksState] = useState<
    NormalizedLandmark[] | null
  >(null)

  const { result, resultRef, landmarksRef } = useFaceLandmarksLoop({
    videoRef,
    landmarkerRef,
    enabled,
    publishState,
  })

  const { pose, poseNorm } = useFacePose({
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

      if (drawDebugOverlay) {
        syncCanvasSize(canvas)
      }

      const now = performance.now()

      const currentResult = resultRef.current
      const { ftm: loopFtm, pose: loopPose } = deriveFacePose(
        currentResult,
        yawSign,
      )
      const lms = landmarksRef.current
      const p = loopPose
      const f = loopFtm

      updateFrameRef(frameRef, now, videoW, videoH, lms, p)

      if (lms) {
        const guideOk = isFaceInsideGuide(lms)

        if (publishState && now - lastUpdateRef.current > FRAME_INTERVAL_MS) {
          setInGuide(guideOk)
          setStatus(guideOk && f && p ? classifyPose(p) : 'none')
          setLandmarksState(lms)
          lastUpdateRef.current = now
        }
      } else {
        if (publishState && now - lastUpdateRef.current > LOST_FACE_RESET_MS) {
          setInGuide(false)
          setStatus('none')
          setLandmarksState(null)
          lastUpdateRef.current = now
        }
      }

      if (drawDebugOverlay) {
        drawLandmarksCover(canvas, lms ?? [], videoW, videoH)

        if (lms) {
          drawRedPointsCover(canvas, lms, [10], videoW, videoH)
        }
      }
    }

    rafRef.current = requestAnimationFrame(loop)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
  }, [
    canvasRef,
    drawDebugOverlay,
    enabled,
    frameRef,
    landmarksRef,
    publishState,
    resultRef,
    videoRef,
    yawSign,
  ])

  return { status, inGuide, pose, poseNorm, landmarks: landmarksState }
}
