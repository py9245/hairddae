import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useEffect, useRef, useState } from 'react'
import { isFaceInsideGuide } from '@/lib/Camera/guide'
import { classifyPose, getHeadPoseFromMatrix } from '@/lib/Camera/pose'
import type { FaceFrame, PoseStatus } from '@/lib/Camera/types'

type DetectForVideoResult = {
  faceLandmarks?: NormalizedLandmark[][]
  facialTransformationMatrixes?: Array<{
    data?: number[] | Float32Array
  }>
}

type LandmarkerLike = {
  detectForVideo: (video: HTMLVideoElement, ts: number) => DetectForVideoResult
}

type PoseLike = {
  pitch?: number
  yaw?: number
  roll?: number
  x?: number
  y?: number
  z?: number
}

const FRAME_INTERVAL = 1000 / 30

function syncCanvasSize(canvas: HTMLCanvasElement) {
  const rect = canvas.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1

  const nextW = Math.round(rect.width * dpr)
  const nextH = Math.round(rect.height * dpr)

  if (canvas.width !== nextW) canvas.width = nextW
  if (canvas.height !== nextH) canvas.height = nextH
}

function updateFrameRef(
  frameRef: React.RefObject<FaceFrame | null> | undefined,
  now: number,
  w: number,
  h: number,
  lms: NormalizedLandmark[] | null,
  pose: FaceFrame['pose'],
) {
  if (!frameRef) return
  frameRef.current = {
    t: now,
    videoW: w,
    videoH: h,
    faceFound: !!lms,
    landmarks: lms ?? [],
    pose,
  }
}

function normDeg0to359(deg: number) {
  const d = ((deg % 360) + 360) % 360
  return Math.round(d)
}

type PoseNorm = { x: number; y: number; z: number } | null

function getCoverRect(
  videoW: number,
  videoH: number,
  canvasW: number,
  canvasH: number,
) {
  const scale = Math.max(canvasW / videoW, canvasH / videoH)
  const drawW = videoW * scale
  const drawH = videoH * scale
  const ox = (canvasW - drawW) / 2
  const oy = (canvasH - drawH) / 2

  return { scale, drawW, drawH, ox, oy }
}

function lmToCoverXY(
  lm: NormalizedLandmark,
  videoW: number,
  videoH: number,
  canvasW: number,
  canvasH: number,
) {
  const { drawW, drawH, ox, oy } = getCoverRect(
    videoW,
    videoH,
    canvasW,
    canvasH,
  )

  return {
    x: ox + lm.x * drawW,
    y: oy + lm.y * drawH,
  }
}

function drawLandmarksCover(
  canvas: HTMLCanvasElement,
  lms: NormalizedLandmark[],
  videoW: number,
  videoH: number,
) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const W = canvas.width
  const H = canvas.height

  ctx.clearRect(0, 0, W, H)
  if (!lms.length) return

  ctx.save()
  ctx.fillStyle = '#8BFF5A'

  for (const lm of lms) {
    const { x, y } = lmToCoverXY(lm, videoW, videoH, W, H)

    ctx.beginPath()
    ctx.arc(x, y, 2.5 * (window.devicePixelRatio || 1), 0, Math.PI * 2)
    ctx.fill()
  }

  ctx.restore()
}

function drawRedPointsCover(
  canvas: HTMLCanvasElement,
  lms: NormalizedLandmark[],
  idxs: number[],
  videoW: number,
  videoH: number,
) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const W = canvas.width
  const H = canvas.height

  ctx.save()
  ctx.fillStyle = 'red'

  for (const i of idxs) {
    const p = lms[i]
    if (!p) continue

    const { x, y } = lmToCoverXY(p, videoW, videoH, W, H)

    ctx.beginPath()
    ctx.arc(x, y, 5 * (window.devicePixelRatio || 1), 0, Math.PI * 2)
    ctx.fill()
  }

  ctx.restore()
}

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
  const lastDetectRef = useRef(0)
  const lastUpdateRef = useRef(0)

  const [status, setStatus] = useState<PoseStatus>('none')
  const [inGuide, setInGuide] = useState(false)
  const [poseNorm, setPoseNorm] = useState<PoseNorm>(null)
  const [landmarks, setLandmarks] = useState<NormalizedLandmark[] | null>(null)

  useEffect(() => {
    const video = videoRef.current
    const canvas = canvasRef.current
    const landmarker = landmarkerRef.current

    if (!enabled || !video || !canvas || !landmarker) return

    const loop = () => {
      rafRef.current = requestAnimationFrame(loop)

      if (video.readyState < 2) return

      const videoW = video.videoWidth
      const videoH = video.videoHeight
      if (videoW <= 0 || videoH <= 0) return

      const now = performance.now()
      if (now - lastDetectRef.current < FRAME_INTERVAL) return
      lastDetectRef.current = now

      syncCanvasSize(canvas)

      const res = landmarker.detectForVideo(video, now)
      const lms = res.faceLandmarks?.[0] ?? null

      const ftm = res.facialTransformationMatrixes?.[0]?.data
      const pose = ftm ? getHeadPoseFromMatrix(ftm, yawSign) : null

      updateFrameRef(frameRef, now, videoW, videoH, lms, pose)

      if (lms) {
        const guideOk = isFaceInsideGuide(lms)

        if (now - lastUpdateRef.current > 120) {
          setInGuide(guideOk)
          setStatus(guideOk && ftm && pose ? classifyPose(pose) : 'none')
          setLandmarks(lms)

          if (pose) {
            const poseValue = pose as PoseLike
            const x = poseValue.pitch ?? poseValue.x ?? 0
            const y = poseValue.yaw ?? poseValue.y ?? 0
            const z = poseValue.roll ?? poseValue.z ?? 0

            setPoseNorm({
              x: normDeg0to359(x),
              y: normDeg0to359(y),
              z: normDeg0to359(z),
            })
          } else {
            setPoseNorm(null)
          }

          lastUpdateRef.current = now
        }
      } else {
        if (now - lastUpdateRef.current > 200) {
          setInGuide(false)
          setStatus('none')
          setPoseNorm(null)
          setLandmarks(null)
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
  }, [enabled, yawSign, videoRef, canvasRef, landmarkerRef, frameRef])

  return { status, inGuide, poseNorm, landmarks }
}
