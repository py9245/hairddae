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
    img: '/hair/0.png',
    thumb: '/hair/0.png',
    label: '헤어 1',
    size: { w: 300, h: 300 },
    anchor: { x: 150, y: 280 },
    baseEyePx: 220,
    offsetPx: { x: -850, y: 40 },
  },
]

function buildFramePayload(
  userId: string,
  poseNorm: PoseNorm | null,
  landmarks: PoseNorm[] | null,
): HairFramePayload | null {
  if (!poseNorm || !landmarks || landmarks.length === 0 || !landmarks[10]) {
    return null
  }

  return {
    user_id: userId,
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
    url: 'ws://localhost:8000/ws',
    enabled: true,
  })

  const displayHairId = pendingHairId ?? appliedHairId

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
    const payload = buildFramePayload(userId, poseNorm, landmarks)
    if (!payload) return

    // console.log('forehead:', JSON.stringify(payload.forehead, null, 2))
    sendFrame(payload)
  }, [poseNorm, landmarks, sendFrame])

  useEffect(() => {
    if (resultJson) {
      console.log('ws json:', resultJson)
    }
  }, [resultJson])

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
          className="pointer-events-none absolute inset-0 h-full w-full -scale-x-100"
        />

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
