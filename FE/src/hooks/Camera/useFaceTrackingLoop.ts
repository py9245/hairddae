import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useEffect, useRef, useState } from 'react'
import {
  type LandmarkerLike,
  useFaceLandmarksLoop,
} from '@/hooks/Camera/useFaceLandmarkersLoop'
import { useFacePose } from '@/hooks/Camera/useFacePose'
import {
  drawLandmarksCover,
  drawRedPointsCover,
  syncCanvasSize,
} from '@/lib/Camera/drawLandmarks'
import { updateFrameRef } from '@/lib/Camera/frame'
import { isFaceInsideGuide } from '@/lib/Camera/guide'
import { classifyPose } from '@/lib/Camera/pose'
import type { FaceFrame, PoseStatus } from '@/lib/Camera/types'

const TARGET_FPS = 15
const FRAME_INTERVAL_MS = 1000 / TARGET_FPS
const LOST_FACE_RESET_MS = FRAME_INTERVAL_MS * 2

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
  const [landmarksState, setLandmarksState] = useState<
    NormalizedLandmark[] | null
  >(null)

  const { result, landmarks } = useFaceLandmarksLoop({
    videoRef,
    landmarkerRef,
    enabled,
  })

  const { ftm, pose, poseNorm } = useFacePose({
    result,
    yawSign,
  })

  // Keep latest rapidly changing values in refs to avoid re-creating the rAF loop
  const landmarksRef = useRef<NormalizedLandmark[] | null>(null)
  const poseRef = useRef<typeof pose>(null)
  const ftmRef = useRef<typeof ftm>(null)

  useEffect(() => {
    landmarksRef.current = landmarks
  }, [landmarks])

  useEffect(() => {
    poseRef.current = pose
  }, [pose])

  useEffect(() => {
    ftmRef.current = ftm
  }, [ftm])

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

      const lms = landmarksRef.current
      const p = poseRef.current
      const f = ftmRef.current

      updateFrameRef(frameRef, now, videoW, videoH, lms, p)

      if (lms) {
        const guideOk = isFaceInsideGuide(lms)

        if (now - lastUpdateRef.current > FRAME_INTERVAL_MS) {
          setInGuide(guideOk)
          setStatus(guideOk && f && p ? classifyPose(p) : 'none')
          setLandmarksState(lms)
          lastUpdateRef.current = now
        }
      } else {
        if (now - lastUpdateRef.current > LOST_FACE_RESET_MS) {
          setInGuide(false)
          setStatus('none')
          setLandmarksState(null)
          lastUpdateRef.current = now
        }
      }

      drawLandmarksCover(canvas, lms ?? [], videoW, videoH)

      if (lms) {
        drawRedPointsCover(canvas, lms, [10], videoW, videoH)
      }
    }

    rafRef.current = requestAnimationFrame(loop)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
  }, [enabled, videoRef, canvasRef, frameRef])

  return { status, inGuide, pose, poseNorm, landmarks: landmarksState }
}
