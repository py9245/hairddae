import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useRouter } from '@tanstack/react-router'
import { Settings, X } from 'lucide-react'
import { type RefObject, useCallback, useRef, useState } from 'react'

import { HairSelector } from '@/components/Camera/HairSelector'
import { ApplyStyleModal } from '@/components/Camera/Modal'
import { useHairInferenceSession } from '@/hooks/Camera/useHairInferenceSession'
import { useHairOverlayCanvas } from '@/hooks/Camera/useHairOverlayCanvas'
import { captureCompositedImage } from '@/lib/Camera/capture'
import { HAIR_ITEMS } from '@/lib/Camera/HairItem'

type Pose = {
  yaw: number
  pitch: number
  roll: number
}

type FaceLandmarksViewProps = {
  videoRef: RefObject<HTMLVideoElement | null>
  canvasRef: RefObject<HTMLCanvasElement | null>
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>
  pose: Pose | null
  landmarks: NormalizedLandmark[] | null
}

export default function FaceLandmarksView({
  videoRef,
  canvasRef,
  overlayCanvasRef,
  pose,
  landmarks,
}: FaceLandmarksViewProps) {
  const router = useRouter()
  const wrapRef = useRef<HTMLDivElement | null>(null)

  const [selectedHairId, setSelectedHairId] = useState(0)
  const [pendingHairId, setPendingHairId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  const displayHairId = pendingHairId ?? selectedHairId

  const hairInference = useHairInferenceSession({
    enabled: displayHairId > 0,
    hairId: displayHairId,
    pose,
    landmarks,
    videoRef,
  })

  const overlayMetrics = useHairOverlayCanvas({
    canvasRef: overlayCanvasRef,
    videoRef,
    landmarks,
    asset: hairInference.asset,
  })

  const handleHairSelect = useCallback((hairId: number) => {
    if (hairId === 0) {
      setPendingHairId(null)
      setSelectedHairId(0)
      setModalOpen(false)
      return
    }

    setPendingHairId(hairId)
    setModalOpen(true)
  }, [])

  const handleModalComplete = useCallback(() => {
    if (pendingHairId == null) {
      setModalOpen(false)
      return
    }

    const nextHairId = pendingHairId

    setSelectedHairId(nextHairId)
    setPendingHairId(null)
    setModalOpen(false)
  }, [pendingHairId])

  const handleCapture = useCallback(() => {
    captureCompositedImage({
      videoRef,
      overlayCanvasRef,
      wrapRef,
      hairItems: HAIR_ITEMS,
      selectedHairId: displayHairId,
    })
  }, [displayHairId, overlayCanvasRef, videoRef])

  const handleClose = useCallback(() => {
    void router.navigate({ to: '/main' })
  }, [router])

  return (
    <div className="grid h-[100dvh] w-full place-items-center bg-neutral-100">
      <div
        ref={wrapRef}
        className="relative h-[100dvh] w-[430px] max-w-full overflow-hidden bg-black"
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

        <canvas
          ref={overlayCanvasRef}
          className="pointer-events-none absolute inset-0 z-10 h-full w-full -scale-x-100"
        />

        <div className="absolute inset-x-0 top-0 z-20 flex items-center justify-between px-4 pt-5">
          <button type="button" onClick={handleClose}>
            <X className="h-10 w-10 text-white" />
          </button>

          <Settings className="h-10 w-10 text-white" />
        </div>

        <div className="absolute top-2 left-2 z-20 rounded bg-black/60 px-2 py-1 text-xs text-white">
          {hairInference.error
            ? hairInference.error
            : hairInference.isConnected
              ? '소켓 연결됨'
              : displayHairId > 0
                ? '소켓 연결 중'
                : '헤어 선택 전'}
        </div>

        <div className="absolute top-10 left-2 z-20 rounded bg-black/60 px-2 py-1 text-[10px] text-white">
          {hairInference.asset
            ? `asset ${hairInference.asset.poseKey}`
            : '준비 완료'}
        </div>

        <div className="absolute top-[4.5rem] left-2 z-20 rounded bg-black/60 px-2 py-1 text-[10px] text-white">
          {`draw ${
            overlayMetrics.drawFps == null
              ? '-'
              : overlayMetrics.drawFps.toFixed(1)
          } fps / rtt ${
            hairInference.metrics.inferenceRttMs == null
              ? '-'
              : `${Math.round(hairInference.metrics.inferenceRttMs)}ms`
          }`}
        </div>

        <div className="absolute top-[6rem] left-2 z-20 rounded bg-black/60 px-2 py-1 text-[10px] text-white">
          {`proc ${
            hairInference.metrics.processedFps == null
              ? '-'
              : hairInference.metrics.processedFps.toFixed(1)
          } fps / bundle ${
            overlayMetrics.bundleReady
              ? overlayMetrics.bundleLoadMs == null
                ? 'ready'
                : `${Math.round(overlayMetrics.bundleLoadMs)}ms`
              : 'loading'
          }`}
        </div>

        <HairSelector
          items={HAIR_ITEMS}
          selectedId={displayHairId}
          onSelect={handleHairSelect}
          onCapture={handleCapture}
        />
      </div>

      {modalOpen && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/20 pb-50">
          <ApplyStyleModal open={modalOpen} onComplete={handleModalComplete} />
        </div>
      )}
    </div>
  )
}
