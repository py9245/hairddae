import { useRouter } from '@tanstack/react-router'
import { Settings, X } from 'lucide-react'
import { type RefObject, useCallback, useEffect, useRef, useState } from 'react'

import { HairSelector } from '@/components/Camera/hair-selector'
import { ApplyStyleModal } from '@/components/Camera/modal'
import { useHairRtcSession } from '@/hooks/Camera/useHairRtcSession'
import { captureCompositedImage } from '@/lib/Camera/capture'
import { HAIR_ITEMS } from '@/lib/Camera/HairItem'

type FaceLandmarksViewProps = {
  stream: MediaStream | null
  transport: string
  videoRef: RefObject<HTMLVideoElement | null>
  canvasRef: RefObject<HTMLCanvasElement | null>
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>
}

export default function FaceLandmarksView({
  stream,
  transport,
  videoRef,
  canvasRef,
  overlayCanvasRef,
}: FaceLandmarksViewProps) {
  const router = useRouter()
  const wrapRef = useRef<HTMLDivElement | null>(null)

  const [selectedHairId, setSelectedHairId] = useState(0)
  const [pendingHairId, setPendingHairId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [isFrameFrozen, setIsFrameFrozen] = useState(false)

  const displayHairId = pendingHairId ?? selectedHairId
  const hairRtc = useHairRtcSession({
    enabled: transport === 'rtc' && !isFrameFrozen && displayHairId > 0,
    hairId: displayHairId > 0 ? displayHairId : null,
    stream,
  })
  const displayStream =
    transport === 'rtc' && hairRtc.remoteStream ? hairRtc.remoteStream : stream

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    if (video.srcObject !== displayStream) {
      video.srcObject = displayStream
    }

    if (isFrameFrozen) {
      video.pause()
      return
    }

    if (displayStream) {
      void video.play().catch(() => {})
    }
  }, [displayStream, isFrameFrozen, videoRef])

  const handleHairSelect = useCallback((hairId: number) => {
    setIsFrameFrozen(false)
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

    setIsFrameFrozen(false)
  }, [displayHairId, overlayCanvasRef, videoRef])

  const handleTopLeftAction = useCallback(() => {
    if (isFrameFrozen) {
      setIsFrameFrozen(false)
      return
    }

    void router.navigate({ to: '/main' })
  }, [isFrameFrozen, router])

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
          <button
            type="button"
            onClick={handleTopLeftAction}
            aria-label={isFrameFrozen ? '캡처 취소' : '닫기'}
          >
            <X className="h-10 w-10 text-white" />
          </button>

          <Settings className="h-10 w-10 text-white" />
        </div>

        {transport === 'rtc' && hairRtc.error ? (
          <div className="absolute inset-x-4 top-18 z-20 rounded-xl bg-black/55 px-3 py-2 text-sm text-white">
            {hairRtc.error}
          </div>
        ) : null}

        <HairSelector
          items={HAIR_ITEMS}
          selectedId={displayHairId}
          frozen={isFrameFrozen}
          onSelect={handleHairSelect}
          onCapture={handleCapture}
          onFreezeChange={setIsFrameFrozen}
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
