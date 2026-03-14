import type { RefObject } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { HairSelector } from '@/components/Camera/HairSelector'
import { Modal } from '@/components/Camera/Modal'
import {
  type HairFramePayload,
  useHairWebSocket,
} from '@/hooks/Camera/useHairWebSocket'

type PoseNorm = { x: number; y: number; z: number }

type HairItem = {
  id: number
  img: string
  thumb: string
  label: string
  size: { w: number; h: number }
  anchor: { x: number; y: number }
  baseEyePx: number
  offsetPx: { x: number; y: number }
}

const HAIR_ITEMS: HairItem[] = [
  {
    id: 0,
    img: '',
    thumb: '',
    label: '없음',
    size: { w: 300, h: 300 },
    anchor: { x: 150, y: 280 },
    baseEyePx: 220,
    offsetPx: { x: 0, y: 0 },
  },
  {
    id: 1,
    img: '/hair/hair.png',
    thumb: '/hair/hair.png',
    label: '헤어 1',
    size: { w: 349, h: 439 },
    anchor: { x: 169.197, y: 155.962 },
    baseEyePx: 220,
    offsetPx: { x: 0, y: 0 },
  },
]

function normalizeAngle360(v: number) {
  const rounded = Math.round(v)
  return ((rounded % 360) + 360) % 360
}

function makeAngleHash(poseNorm: PoseNorm) {
  const x = normalizeAngle360(poseNorm.x)
  const y = normalizeAngle360(poseNorm.y)
  const z = normalizeAngle360(poseNorm.z)
  return x * 360 ** 2 + y * 360 + z
}

function buildFramePayload(
  userId: string,
  frameId: number,
  videoEl: HTMLVideoElement | null,
  poseNorm: PoseNorm | null,
  landmarks: PoseNorm[] | null,
):
  | (HairFramePayload & {
      frame_id: number
      camera: { w: number; h: number }
      angle_hash: number
    })
  | null {
  if (!poseNorm || !landmarks || landmarks.length === 0 || !landmarks[10]) {
    return null
  }

  const w = videoEl?.videoWidth ?? 0
  const h = videoEl?.videoHeight ?? 0

  return {
    user_id: userId,
    frame_id: frameId,
    camera: {
      w,
      h,
    },
    angle_hash: makeAngleHash(poseNorm),
    angle: {
      pitch: poseNorm.x,
      yaw: poseNorm.y,
      roll: poseNorm.z,
    },
    forehead: {
      x: landmarks[10].x,
      y: landmarks[10].y,
      z: landmarks[10].z ?? 0,
    },
    landmark: landmarks.map((lm) => ({
      x: lm.x,
      y: lm.y,
      z: lm.z ?? 0,
    })),
  }
}

export default function FaceLandmarksView({
  videoRef,
  canvasRef,
  poseNorm,
  landmarks,
}: {
  videoRef: RefObject<HTMLVideoElement | null>
  canvasRef: RefObject<HTMLCanvasElement | null>
  poseNorm: PoseNorm | null
  landmarks: PoseNorm[] | null
}) {
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const frameIdRef = useRef(0)
  const userId = 'user-123'

  const [appliedHairId, setAppliedHairId] = useState(0)
  const [pendingHairId, setPendingHairId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  const {
    isConnected,
    resultPng,
    resultJson,
    error: wsError,
    sendFrame,
  } = useHairWebSocket({
    enabled: true,
  })

  const displayHairId = pendingHairId ?? appliedHairId

  const selectedHair = useMemo(() => {
    return HAIR_ITEMS.find((item) => item.id === displayHairId) ?? null
  }, [displayHairId])

  const pendingHair = useMemo(() => {
    if (pendingHairId == null) return null
    return HAIR_ITEMS.find((item) => item.id === pendingHairId) ?? null
  }, [pendingHairId])

  const handleHairSelect = useCallback(
    (nextId: number) => {
      if (modalOpen) return
      if (nextId === appliedHairId) return

      setPendingHairId(nextId)
      setModalOpen(true)
    },
    [appliedHairId, modalOpen],
  )

  const handleModalComplete = useCallback(() => {
    if (pendingHairId != null) {
      setAppliedHairId(pendingHairId)
    }
    setPendingHairId(null)
    setModalOpen(false)
  }, [pendingHairId])

  useEffect(() => {
    frameIdRef.current += 1

    const payload = buildFramePayload(
      userId,
      frameIdRef.current,
      videoRef.current,
      poseNorm,
      landmarks,
    )

    if (!payload) return
    sendFrame(payload)
  }, [poseNorm, landmarks, sendFrame, videoRef])

  useEffect(() => {
    if (resultJson) {
      console.log('ws json:', resultJson)
    }
  }, [resultJson])

  const foreheadPx = useMemo(() => {
    const wrap = wrapRef.current
    const forehead = landmarks?.[10]

    if (!wrap || !forehead) return null

    const rect = wrap.getBoundingClientRect()

    return {
      x: (1 - forehead.x) * rect.width,
      y: forehead.y * rect.height,
    }
  }, [landmarks])

  return (
    <div className="grid h-screen w-screen place-items-center overflow-hidden">
      <div
        ref={wrapRef}
        className="relative h-screen w-[430px] overflow-hidden bg-black"
      >
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="block h-full w-full object-cover -scale-x-100"
        />

        <canvas
          ref={canvasRef}
          className="pointer-events-none absolute inset-0 hidden h-full w-full -scale-x-100"
        />

        {selectedHair?.img &&
          foreheadPx &&
          (() => {
            const flippedAnchorX = selectedHair.size.w - selectedHair.anchor.x

            return (
              <img
                src={selectedHair.img}
                alt={selectedHair.label}
                className="pointer-events-none absolute z-10"
                style={{
                  width: `${selectedHair.size.w}px`,
                  height: `${selectedHair.size.h}px`,
                  left: `${foreheadPx.x - flippedAnchorX - selectedHair.offsetPx.x}px`,
                  top: `${foreheadPx.y - selectedHair.anchor.y + selectedHair.offsetPx.y}px`,
                }}
              />
            )
          })()}

        {resultPng && (
          <img
            src={resultPng}
            alt="ai result"
            className="pointer-events-none absolute inset-0 h-full w-full object-cover"
          />
        )}

        <div className="absolute top-2 left-2 z-20 rounded bg-black/60 px-2 py-1 text-xs text-white">
          {isConnected ? 'WS connected' : 'WS disconnected'}
        </div>

        {wsError && (
          <div className="absolute top-10 left-2 z-20 rounded bg-red-600/80 px-2 py-1 text-xs text-white">
            {wsError}
          </div>
        )}

        <HairSelector
          items={HAIR_ITEMS}
          selectedId={displayHairId}
          onSelect={handleHairSelect}
        />
      </div>

      <Modal
        open={modalOpen}
        targetLabel={pendingHair?.label}
        onComplete={handleModalComplete}
      />
    </div>
  )
}
