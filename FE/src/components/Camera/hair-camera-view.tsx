import { useRouter } from '@tanstack/react-router'
import { X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { HairCameraStage } from '@/components/Camera/hair-camera-stage'
import { HairSelector } from '@/components/Camera/hair-selector'
import { ApplyStyleModal, CameraNoticeModal } from '@/components/Camera/modal'
import { GuideModal } from '@/components/guide-modal'
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

const CAMERA_GUIDE_DISMISSED_KEY = 'camera-guide-dismissed'

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
  const finishTimerRef = useRef<number | null>(null)

  const [selectedHairId, setSelectedHairId] = useState(0)
  const [pendingHairId, setPendingHairId] = useState<number | null>(null)
  const [hairItems, setHairItems] = useState<HairItem[]>(HAIR_ITEMS)
  const [isHairItemsLoading, setIsHairItemsLoading] = useState(true)
  const [hairItemsError, setHairItemsError] = useState<{
    title: string
    description: string[]
  } | null>(null)
  const [isGuideModalOpen, setIsGuideModalOpen] = useState(false)
  const [isFrameFrozen, setIsFrameFrozen] = useState(false)
  const [uiScale, setUiScale] = useState(1)

  const displayHairId = pendingHairId ?? selectedHairId
  const selectedHairItem =
    hairItems.find((item) => item.id === displayHairId) ?? null

  const stageStream = useViewportCaptureStream({
    enabled: cameraReady && displayHairId > 0,
    fps: RTC_STAGE_FPS,
    width: RTC_STAGE_WIDTH,
    height: RTC_STAGE_HEIGHT,
    mirror: false,
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
    const dismissed = window.localStorage.getItem(CAMERA_GUIDE_DISMISSED_KEY)

    if (dismissed === 'true') {
      return
    }

    setIsGuideModalOpen(true)
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    setIsHairItemsLoading(true)
    setHairItemsError(null)
    fetchHairItems(controller.signal)
      .then((items) => {
        if (items.length <= 1) {
          setHairItems(HAIR_ITEMS)
          setHairItemsError({
            title: '헤어 스타일 목록을 불러올 수 없어요',
            description: [
              '현재 적용 가능한 헤어 스타일 정보가 없습니다.',
              '홈 화면에서 적용하기를 선택해 주세요.',
            ],
          })
          return
        }

        setHairItems(items)
      })
      .catch((error) => {
        console.error('hair item load failed:', error)
        setHairItems(HAIR_ITEMS)
        setHairItemsError({
          title: '헤어 스타일 목록을 불러올 수 없어요',
          description: ['네트워크 상태를 확인한 뒤 다시 시도해 주세요.'],
        })
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
      mirror: hasRemoteVideo ? false : RTC_STAGE_MIRRORED,
      selectedHairId: displayHairId,
    })

    setIsFrameFrozen(false)
  }, [displayHairId, hairItems, hasRemoteVideo, remoteVideoRef, videoRef])

  const handleTopLeftAction = useCallback(() => {
    if (isFrameFrozen) {
      setIsFrameFrozen(false)
      return
    }

    void router.navigate({ to: '/main' })
  }, [isFrameFrozen, router])

  const modalOpen = pendingHairId != null && pendingHairId > 0
  const hairItemsErrorOpen = hairItemsError != null
  const hasAppliedPendingHair =
    modalOpen &&
    pendingHairId != null &&
    hairRtc.appliedHairId === pendingHairId
  const hasHelloApplied =
    modalOpen && pendingHairId != null && hairRtc.hasHelloApplied
  const hasRenderedPendingHair =
    modalOpen &&
    pendingHairId != null &&
    hairRtc.isRenderReady &&
    remoteDisplayReady
  const rtcApplyReady =
    hasAppliedPendingHair || hasHelloApplied || hasRenderedPendingHair

  useEffect(() => {
    if (finishTimerRef.current != null) {
      window.clearTimeout(finishTimerRef.current)
      finishTimerRef.current = null
    }

    if (!rtcApplyReady) {
      return
    }

    finishTimerRef.current = window.setTimeout(() => {
      finishTimerRef.current = null
      handleModalFinish()
    }, 600)

    return () => {
      if (finishTimerRef.current != null) {
        window.clearTimeout(finishTimerRef.current)
        finishTimerRef.current = null
      }
    }
  }, [handleModalFinish, rtcApplyReady])

  const handleGuideModalClose = useCallback(() => {
    setIsGuideModalOpen(false)
  }, [])

  const handleGuideModalDismiss = useCallback(() => {
    window.localStorage.setItem(CAMERA_GUIDE_DISMISSED_KEY, 'true')
    setIsGuideModalOpen(false)
  }, [])

  return (
    <main className="app-frame-page relative flex min-h-full items-center justify-center overflow-hidden bg-black text-white">
      <div className="relative flex h-full min-h-full w-full items-center justify-center overflow-hidden px-0">
        <div
          ref={wrapRef}
          className="relative aspect-[9/16] w-full max-w-[min(100%,calc((100dvh-1rem)*9/16))] overflow-hidden bg-black shadow-[0_24px_80px_rgba(2,6,23,0.45)]"
        >
          <HairCameraStage
            videoRef={videoRef}
            remoteVideoRef={remoteVideoRef}
            hasRemoteVideo={hasRemoteVideo}
            localMirrored={RTC_STAGE_MIRRORED}
            remoteMirrored={false}
          />

          <Header
            rightAction={
              <Button
                type="button"
                variant="camera-back"
                size="camera-icon"
                onClick={handleTopLeftAction}
                data-testid="camera-back-button"
                aria-label={isFrameFrozen ? '캡처 취소' : '닫기'}
              >
                <X className="size-12 text-white" />
              </Button>
            }
          />

          <HairSelector
            items={hairItems}
            selectedId={displayHairId}
            loading={isHairItemsLoading}
            frozen={isFrameFrozen}
            onSelect={handleHairSelect}
            onCapture={handleCapture}
            onFreezeChange={setIsFrameFrozen}
          />

          {isGuideModalOpen ? (
            <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
              <GuideModal
                open={isGuideModalOpen}
                onClose={handleGuideModalClose}
                onDismiss={handleGuideModalDismiss}
                scale={uiScale}
              />
            </div>
          ) : null}

          {modalOpen ? (
            <div className="pointer-events-none absolute inset-0 z-40 flex items-center justify-center bg-black/20 px-4">
              <ApplyStyleModal
                key={pendingHairId ?? 'pending-hair'}
                open={modalOpen}
                completed={rtcApplyReady}
                onFinish={handleModalFinish}
                onClose={handleModalClose}
                scale={uiScale}
              />
            </div>
          ) : null}

          {hairItemsErrorOpen ? (
            <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/20 px-4">
              <CameraNoticeModal
                open={hairItemsErrorOpen}
                title={hairItemsError.title}
                description={hairItemsError.description}
                onConfirm={() => {
                  void router.navigate({ to: '/main' })
                }}
                onClose={() => {
                  void router.navigate({ to: '/main' })
                }}
                scale={uiScale}
              />
            </div>
          ) : null}
        </div>
      </div>
    </main>
  )
}
