import { useRouter } from '@tanstack/react-router'
import { Settings, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { HairCameraStage } from '@/components/Camera/hair-camera-stage'
import { HairSelector } from '@/components/Camera/hair-selector'
import { ApplyStyleModal } from '@/components/Camera/modal'
import {
  type CameraSettingOption,
  CameraSettingsModal,
} from '@/components/Camera/setting-modal'
import { Header } from '@/components/header'
import { Button } from '@/components/ui/button'
import { useHairRtcDisplay } from '@/hooks/Camera/useHairRtcDisplay'
import { useHairRtcSession } from '@/hooks/Camera/useHairRtcSession'
import { useViewportCaptureStream } from '@/hooks/Camera/useViewportCaptureStream'
import { captureCompositedImage } from '@/lib/Camera/capture'
import {
  fetchHairItems,
  HAIR_ITEMS,
  type HairItem,
} from '@/lib/Camera/HairItem'
import {
  RTC_STAGE_FPS,
  RTC_STAGE_HEIGHT,
  RTC_STAGE_MIRRORED,
  RTC_STAGE_WIDTH,
} from '@/lib/Camera/runtime'

type HairCameraViewProps = {
  videoRef: React.RefObject<HTMLVideoElement | null>
  cameraStream: MediaStream | null
  cameraReady: boolean
  cameraError: unknown
  initialHairId?: number | null
  autoSelectFirstHair?: boolean
}

export function HairCameraView({
  videoRef,
  cameraStream: _cameraStream,
  cameraReady,
  cameraError: _cameraError,
  initialHairId = null,
  autoSelectFirstHair = false,
}: HairCameraViewProps) {
  const router = useRouter()
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const hasHandledInitialSelectionRef = useRef(false)

  const [selectedHairId, setSelectedHairId] = useState(0)
  const [pendingHairId, setPendingHairId] = useState<number | null>(null)
  const [hairItems, setHairItems] = useState<HairItem[]>(HAIR_ITEMS)
  const [isHairItemsLoading, setIsHairItemsLoading] = useState(true)
  const [isFrameFrozen, setIsFrameFrozen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [stageMirrored, setStageMirrored] = useState(RTC_STAGE_MIRRORED)
  const [uiScale, setUiScale] = useState(1)

  const displayHairId = pendingHairId ?? selectedHairId
  const selectedHairItem =
    hairItems.find((item) => item.id === displayHairId) ?? null

  const stageStream = useViewportCaptureStream({
    enabled: cameraReady && displayHairId > 0,
    fps: RTC_STAGE_FPS,
    width: RTC_STAGE_WIDTH,
    height: RTC_STAGE_HEIGHT,
    mirror: stageMirrored,
    sourceVideoRef: videoRef,
  })

  const hairRtc = useHairRtcSession({
    enabled: displayHairId > 0,
    hairId: displayHairId > 0 ? displayHairId : null,
    datasetCode: selectedHairItem?.datasetCode ?? null,
    stream: stageStream,
  })

  const { remoteVideoRef, remoteDisplayReady, hasRemoteVideo } =
    useHairRtcDisplay({
      localVideoRef: videoRef,
      remoteStream: hairRtc.remoteStream,
      isRenderReady: hairRtc.isRenderReady,
      isFrameFrozen,
    })

  useEffect(() => {
    const element = wrapRef.current
    if (!element) {
      return
    }

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) {
        return
      }

      setUiScale(Math.min(entry.contentRect.width / 380, 1))
    })

    observer.observe(element)

    return () => {
      observer.disconnect()
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    setIsHairItemsLoading(true)
    fetchHairItems(controller.signal)
      .then((items) => {
        setHairItems(items.length > 1 ? items : HAIR_ITEMS)
      })
      .catch((error) => {
        console.error('hair item load failed:', error)
        setHairItems(HAIR_ITEMS)
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsHairItemsLoading(false)
        }
      })

    return () => {
      controller.abort()
    }
  }, [])

  useEffect(() => {
    if (hasHandledInitialSelectionRef.current || isHairItemsLoading) {
      return
    }

    const targetHairId =
      initialHairId != null &&
      hairItems.some((item) => item.id === initialHairId)
        ? initialHairId
        : autoSelectFirstHair
          ? (hairItems.find((item) => item.id > 0)?.id ?? null)
          : null

    hasHandledInitialSelectionRef.current = true

    if (targetHairId == null) {
      return
    }

    setIsFrameFrozen(false)
    setPendingHairId(targetHairId)
    setSelectedHairId(0)

    void router.navigate({
      to: '/camera',
      replace: true,
      search: {},
    })
  }, [
    autoSelectFirstHair,
    hairItems,
    initialHairId,
    isHairItemsLoading,
    router,
  ])

  const handleHairSelect = useCallback((hairId: number) => {
    setIsFrameFrozen(false)

    if (hairId <= 0) {
      setPendingHairId(null)
      setSelectedHairId(0)
      return
    }

    setPendingHairId(hairId)
  }, [])

  const handleModalFinish = useCallback(() => {
    if (pendingHairId == null) {
      return
    }

    setSelectedHairId(pendingHairId)
    setPendingHairId(null)
  }, [pendingHairId])

  const handleModalClose = useCallback(() => {
    setPendingHairId(null)
    setIsFrameFrozen(false)
  }, [])

  const handleCapture = useCallback(() => {
    captureCompositedImage({
      videoRef: hasRemoteVideo ? remoteVideoRef : videoRef,
      wrapRef,
      hairItems,
      mirror: hasRemoteVideo ? false : stageMirrored,
      selectedHairId: displayHairId,
    })

    setIsFrameFrozen(false)
  }, [
    displayHairId,
    hairItems,
    hasRemoteVideo,
    remoteVideoRef,
    stageMirrored,
    videoRef,
  ])

  const handleTopLeftAction = useCallback(() => {
    if (isFrameFrozen) {
      setIsFrameFrozen(false)
      return
    }

    void router.navigate({ to: '/main' })
  }, [isFrameFrozen, router])

  const modalOpen = pendingHairId != null && pendingHairId > 0
  const rtcApplyReady =
    modalOpen &&
    pendingHairId != null &&
    hairRtc.isConnected &&
    !hairRtc.error &&
    (hairRtc.appliedHairId === pendingHairId ||
      (hairRtc.isRenderReady && remoteDisplayReady))

  const resolutionOptions: CameraSettingOption[] = [
    {
      value: `${RTC_STAGE_WIDTH}x${RTC_STAGE_HEIGHT}`,
      label: `${RTC_STAGE_WIDTH}x${RTC_STAGE_HEIGHT}`,
    },
  ]

  return (
    <main className="app-frame-page relative overflow-hidden bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.14),transparent_34%),linear-gradient(180deg,#1f2937_0%,#020617_100%)] text-white">
      <div className="relative flex h-full w-full items-center justify-center overflow-hidden px-0">
        <div
          ref={wrapRef}
          className="relative aspect-[9/16] w-full max-w-[min(100%,calc((100dvh-1rem)*9/16))] overflow-hidden bg-black shadow-[0_24px_80px_rgba(2,6,23,0.45)]"
        >
          <HairCameraStage
            videoRef={videoRef}
            remoteVideoRef={remoteVideoRef}
            hasRemoteVideo={hasRemoteVideo}
            localMirrored={stageMirrored}
            remoteMirrored={false}
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
                onClick={() => {
                  setSettingsOpen(true)
                }}
                aria-label="설정 열기"
              >
                <Settings className="size-12 text-white" />
              </Button>
            }
          />

          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-40 bg-gradient-to-b from-black/50 via-black/20 to-transparent" />

          <HairSelector
            items={hairItems}
            selectedId={displayHairId}
            loading={isHairItemsLoading}
            frozen={isFrameFrozen}
            onSelect={handleHairSelect}
            onCapture={handleCapture}
            onFreezeChange={setIsFrameFrozen}
          />

          {modalOpen ? (
            <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/20 px-4">
              <ApplyStyleModal
                open={modalOpen}
                completed={rtcApplyReady}
                onFinish={handleModalFinish}
                onClose={handleModalClose}
                scale={uiScale}
              />
            </div>
          ) : null}

          <CameraSettingsModal
            open={settingsOpen}
            mirrored={stageMirrored}
            onMirroredChange={setStageMirrored}
            selectedResolutionId={resolutionOptions[0].value}
            selectedFps={RTC_STAGE_FPS}
            resolutionOptions={resolutionOptions}
            fpsOptions={[RTC_STAGE_FPS]}
            onResolutionChange={() => {}}
            onFpsChange={() => {}}
            onClose={() => {
              setSettingsOpen(false)
            }}
          />
        </div>
      </div>
    </main>
  )
}
