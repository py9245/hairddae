import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
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

type Pose = {
  yaw: number
  pitch: number
  roll: number
}

type FaceLandmarksViewProps = {
  stream: MediaStream | null
  videoRef: RefObject<HTMLVideoElement | null>
  canvasRef: RefObject<HTMLCanvasElement | null>
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>
  pose: Pose | null
  landmarks: NormalizedLandmark[] | null
}

function formatDebugNumber(
  value: number | null,
  options: Intl.NumberFormatOptions = { maximumFractionDigits: 1 },
) {
  if (value == null || !Number.isFinite(value)) {
    return '-'
  }

  return new Intl.NumberFormat('ko-KR', options).format(value)
}

export default function FaceLandmarksView({
  stream,
  videoRef,
  canvasRef,
  overlayCanvasRef,
  pose: _pose,
  landmarks: _landmarks,
}: FaceLandmarksViewProps) {
  const router = useRouter()
  const wrapRef = useRef<HTMLDivElement | null>(null)

  const [selectedHairId, setSelectedHairId] = useState(0)
  const [pendingHairId, setPendingHairId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [hairItems, setHairItems] = useState<HairItem[]>(HAIR_ITEMS)
  const [isFrameFrozen, setIsFrameFrozen] = useState(false)

  const displayHairId = pendingHairId ?? selectedHairId

  const hairRtc = useHairRtcSession({
    enabled: displayHairId > 0,
    hairId: displayHairId > 0 ? displayHairId : null,
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
  const showRtcDebug =
    typeof window !== 'undefined' &&
    new URLSearchParams(window.location.search).get('rtcDebug') === '1'

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
      mirror: true,
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
        className="relative h-[100dvh] w-[430px] max-w-full overflow-hidden bg-black"
      >
        <HairCameraStage
          videoRef={videoRef}
          remoteVideoRef={remoteVideoRef}
          canvasRef={canvasRef}
          overlayCanvasRef={overlayCanvasRef}
          hasRemoteVideo={hasRemoteVideo}
        />

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

        {showRtcDebug ? (
          <div className="absolute inset-x-4 top-32 z-20 rounded-xl bg-black/70 p-3 font-mono text-[11px] leading-4 text-white">
            <div>
              state={hairRtc.connectionState} processed_fps=
              {formatDebugNumber(hairRtc.metrics.processedFps)} queue=
              {hairRtc.metrics.queueDepth} drop={hairRtc.metrics.droppedPendingCount}
            </div>
            <div>
              rtc_rtt_ms=
              {formatDebugNumber(hairRtc.metrics.transportRoundTripTimeMs)} one_way_ms=
              {formatDebugNumber(hairRtc.metrics.estimatedOneWayTransportMs)} server_ms=
              {formatDebugNumber(hairRtc.metrics.serverProcessingMs)}
            </div>
            <div>
              out_kbps={formatDebugNumber(hairRtc.metrics.outboundBitrateKbps)} in_kbps=
              {formatDebugNumber(hairRtc.metrics.inboundBitrateKbps)} avail_out_kbps=
              {formatDebugNumber(hairRtc.metrics.availableOutgoingBitrateKbps)}
            </div>
            <div>
              out_fps={formatDebugNumber(hairRtc.metrics.outboundFramesPerSecond)} in_fps=
              {formatDebugNumber(hairRtc.metrics.inboundFramesPerSecond)} out_res=
              {hairRtc.metrics.outboundFrameWidth ?? '-'}x
              {hairRtc.metrics.outboundFrameHeight ?? '-'} in_res=
              {hairRtc.metrics.inboundFrameWidth ?? '-'}x
              {hairRtc.metrics.inboundFrameHeight ?? '-'}
            </div>
            {hairRtc.debugLogs.length > 0 ? (
              <div className="mt-2 border-t border-white/20 pt-2">
                {hairRtc.debugLogs.map((log) => (
                  <div key={`${log.atIso}-${log.summary}`} className="truncate">
                    [{log.atIso.slice(11, 19)}] {log.summary}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        <HairSelector
          items={hairItems}
          selectedId={displayHairId}
          frozen={isFrameFrozen}
          onSelect={handleHairSelect}
          onCapture={handleCapture}
          onFreezeChange={setIsFrameFrozen}
        />
      </div>

      {modalOpen && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/20 pb-50">
          <ApplyStyleModal
            open={modalOpen}
            completed={rtcApplyReady}
            onFinish={handleModalFinish}
          />
        </div>
      )}
    </div>
  )
}
