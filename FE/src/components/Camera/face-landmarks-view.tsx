// face-landmarks-view.tsx
import { useRouter } from '@tanstack/react-router'
import { Settings, X } from 'lucide-react'
import { type RefObject, useCallback, useEffect, useRef, useState } from 'react'

import { HairCameraStage } from '@/components/Camera/hair-camera-stage'
import { HairRtcDebugPanel } from '@/components/Camera/hair-rtc-debug-panel'
import { HairSelector } from '@/components/Camera/hair-selector'
import { ApplyStyleModal } from '@/components/Camera/modal'
import { Header } from '@/components/header'
import { Button } from '@/components/ui/button'
import { useHairRtcDisplay } from '@/hooks/Camera/useHairRtcDisplay'
import { useHairRtcSession } from '@/hooks/Camera/useHairRtcSession'
import { captureCompositedImage } from '@/lib/Camera/capture'
import {
  fetchHairItems,
  HAIR_ITEMS,
  type HairItem,
} from '@/lib/Camera/HairItem'

type FaceLandmarksViewProps = {
  stream: MediaStream | null
  videoRef: RefObject<HTMLVideoElement | null>
  canvasRef: RefObject<HTMLCanvasElement | null>
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>
}

const BASE_UI_WIDTH = 430
const BASE_UI_HEIGHT = (BASE_UI_WIDTH * 20) / 9

export default function FaceLandmarksView({
  stream,
  videoRef,
  canvasRef,
  overlayCanvasRef,
}: FaceLandmarksViewProps) {
  const router = useRouter()
  const wrapRef = useRef<HTMLDivElement | null>(null)

  const [uiScale, setUiScale] = useState(1)
  const [selectedHairId, setSelectedHairId] = useState(0)
  const [pendingHairId, setPendingHairId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [hairItems, setHairItems] = useState<HairItem[]>(HAIR_ITEMS)
  const [isFrameFrozen, setIsFrameFrozen] = useState(false)

  const displayHairId = pendingHairId ?? selectedHairId

  const hairRtc = useHairRtcSession({
    enabled: displayHairId > 0,
    hairId: displayHairId,
    stream,
  })

  const {
    remoteVideoRef,
    remoteVideoReady,
    remoteDisplayReady,
    remoteVideoSize,
    hasRemoteVideo,
  } = useHairRtcDisplay({
    localVideoRef: videoRef,
    remoteStream: hairRtc.remoteStream,
    isRenderReady: hairRtc.isRenderReady,
    isFrameFrozen,
  })

  const rtcApplyReady =
    modalOpen &&
    pendingHairId != null &&
    hairRtc.isRenderReady &&
    remoteDisplayReady

  useEffect(() => {
    const controller = new AbortController()

    fetchHairItems(controller.signal)
      .then((items) => {
        setHairItems(items.length > 1 ? items : HAIR_ITEMS)
      })
      .catch((error) => {
        console.error('hair item load failed:', error)
        setHairItems(HAIR_ITEMS)
      })

    return () => {
      controller.abort()
    }
  }, [])

  useEffect(() => {
    const element = wrapRef.current
    if (!element) return

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return

      const { width } = entry.contentRect
      setUiScale(width / BASE_UI_WIDTH)
    })

    observer.observe(element)

    return () => {
      observer.disconnect()
    }
  }, [])

  const handleHairSelect = useCallback((hairId: number) => {
    setIsFrameFrozen(false)
    setPendingHairId(hairId)
    setModalOpen(true)
  }, [])

  const handleModalFinish = useCallback(() => {
    if (pendingHairId == null) {
      setModalOpen(false)
      return
    }

    setSelectedHairId(pendingHairId)
    setPendingHairId(null)
    setModalOpen(false)
  }, [pendingHairId])

  const handleCapture = useCallback(() => {
    captureCompositedImage({
      videoRef: hasRemoteVideo ? remoteVideoRef : videoRef,
      overlayCanvasRef,
      wrapRef,
      hairItems,
      selectedHairId: displayHairId,
    })

    setIsFrameFrozen(false)
  }, [
    displayHairId,
    hairItems,
    hasRemoteVideo,
    overlayCanvasRef,
    remoteVideoRef,
    videoRef,
  ])

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
        className="relative h-[100dvh] aspect-[9/20] overflow-hidden bg-black"
      >
        <HairCameraStage
          videoRef={videoRef}
          remoteVideoRef={remoteVideoRef}
          canvasRef={canvasRef}
          overlayCanvasRef={overlayCanvasRef}
          hasRemoteVideo={hasRemoteVideo}
        />

        <div className="absolute inset-0 z-20 overflow-hidden">
          <div
            className="absolute left-0 top-0"
            style={{
              width: `${BASE_UI_WIDTH}px`,
              height: `${BASE_UI_HEIGHT}px`,
              transform: `scale(${uiScale})`,
              transformOrigin: 'top left',
            }}
          >
            <Header
              leftAction={
                <Button
                  type="button"
                  variant="camera-back"
                  size="camera-icon"
                  onClick={handleTopLeftAction}
                  aria-label={isFrameFrozen ? '캡처 취소' : '닫기'}
                >
                  <X className="size-12 text-white" />
                </Button>
              }
              rightAction={
                <Button
                  type="button"
                  variant="camera-setting"
                  size="camera-icon"
                  aria-label="설정 열기"
                >
                  <Settings className="size-12 text-white" />
                </Button>
              }
            />

            <HairRtcDebugPanel
              error={hairRtc.error}
              isConnected={hairRtc.isConnected}
              displayHairId={displayHairId}
              asset={hairRtc.asset}
              connectionState={hairRtc.connectionState}
              metrics={hairRtc.metrics}
              hasRemoteVideo={remoteDisplayReady}
              remoteVideoReady={remoteVideoReady}
              isRenderReady={hairRtc.isRenderReady}
              remoteVideoSize={remoteVideoSize}
            />

            <HairSelector
              items={hairItems}
              selectedId={displayHairId}
              frozen={isFrameFrozen}
              onSelect={handleHairSelect}
              onCapture={handleCapture}
              onFreezeChange={setIsFrameFrozen}
            />
          </div>
        </div>

        {modalOpen && (
          <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/20">
            <ApplyStyleModal
              open={modalOpen}
              completed={rtcApplyReady}
              onFinish={handleModalFinish}
            />
          </div>
        )}
      </div>
    </div>
  )
}