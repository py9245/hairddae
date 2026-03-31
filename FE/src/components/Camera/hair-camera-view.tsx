import { useMutation } from '@tanstack/react-query'
import { useRouter } from '@tanstack/react-router'
import { X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { CaptureCompleteModal } from '@/components/Camera/capture-complete-modal'
import { HairCameraStage } from '@/components/Camera/hair-camera-stage'
import { HairSelector } from '@/components/Camera/hair-selector'
import { ApplyStyleModal, CameraNoticeModal } from '@/components/Camera/modal'
import { GuideModal } from '@/components/guide-modal'
import { Header } from '@/components/header'
import { Button } from '@/components/ui/button'
import { useHairRtcDisplay } from '@/hooks/Camera/useHairRtcDisplay'
import { useHairRtcSession } from '@/hooks/Camera/useHairRtcSession'
import { useViewportCaptureStream } from '@/hooks/Camera/useViewportCaptureStream'
import { fetchMe } from '@/lib/auth'
import { postAiUpgrade } from '@/lib/Camera/ai-upgrade'
import {
  canvasToBlob,
  captureCompositedImage,
  downloadCanvasImage,
  drawCompositedSourceToCanvas,
  drawImageUrlToCanvas,
} from '@/lib/Camera/capture'
import {
  fetchHairItems,
  HAIR_ITEMS,
  type HairItem,
} from '@/lib/Camera/HairItem'
import { getOrCreateDeviceId } from '@/lib/Camera/inference'
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

type CameraGuidePreference = {
  dismissed?: boolean
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
  const frozenFrameCanvasRef = useRef<HTMLCanvasElement | null>(null)
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
  const [isCaptureCompleteModalOpen, setIsCaptureCompleteModalOpen] =
    useState(false)
  const [aiEnhanceMessage, setAiEnhanceMessage] = useState<string | null>(null)
  const [isGuideModalOpen, setIsGuideModalOpen] = useState(false)
  const [isFrameFrozen, setIsFrameFrozen] = useState(false)
  const [uiScale, setUiScale] = useState(1)
  const aiUpgradeMutation = useMutation({
    mutationFn: postAiUpgrade,
  })

  const readGuidePreferences = useCallback(() => {
    try {
      const raw = window.localStorage.getItem(CAMERA_GUIDE_DISMISSED_KEY)
      if (!raw) {
        return {}
      }

      return JSON.parse(raw) as Record<string, CameraGuidePreference>
    } catch {
      return {}
    }
  }, [])

  const writeGuidePreference = useCallback(
    (userId: string, nextPreference: CameraGuidePreference) => {
      const preferences = readGuidePreferences()
      preferences[userId] = nextPreference
      window.localStorage.setItem(
        CAMERA_GUIDE_DISMISSED_KEY,
        JSON.stringify(preferences),
      )
    },
    [readGuidePreferences],
  )

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
    void (async () => {
      const me = await fetchMe().catch(() => null)
      if (!me) {
        return
      }

      const dismissed = readGuidePreferences()[me.userID]?.dismissed
      if (dismissed) {
        return
      }

      setIsGuideModalOpen(true)
    })()
  }, [readGuidePreferences])

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

  const handleFreezeChange = useCallback(
    (nextFrozen: boolean) => {
      if (!nextFrozen) {
        setIsFrameFrozen(false)
        return
      }

      const wrap = wrapRef.current
      const frozenCanvas = frozenFrameCanvasRef.current
      const sourceVideo = hasRemoteVideo
        ? remoteVideoRef.current
        : videoRef.current

      if (!wrap || !frozenCanvas || !sourceVideo) {
        return
      }

      const didDraw = drawCompositedSourceToCanvas({
        source: sourceVideo,
        outputCanvas: frozenCanvas,
        width: wrap.clientWidth,
        height: wrap.clientHeight,
        mirror: hasRemoteVideo ? false : RTC_STAGE_MIRRORED,
      })

      if (!didDraw) {
        return
      }

      setIsFrameFrozen(true)
    },
    [hasRemoteVideo, remoteVideoRef, videoRef],
  )

  const handleHairSelect = useCallback(
    (hairId: number) => {
      handleFreezeChange(false)

      if (hairId <= 0) {
        setPendingHairId(null)
        setSelectedHairId(0)
        return
      }

      setPendingHairId(hairId)
    },
    [handleFreezeChange],
  )

  const handleModalFinish = useCallback(() => {
    if (pendingHairId == null) {
      return
    }

    setSelectedHairId(pendingHairId)
    setPendingHairId(null)
  }, [pendingHairId])

  const handleModalClose = useCallback(() => {
    setPendingHairId(null)
    handleFreezeChange(false)
  }, [handleFreezeChange])

  const handleCapture = useCallback(() => {
    const frozenCanvas = frozenFrameCanvasRef.current

    if (isFrameFrozen && frozenCanvas) {
      downloadCanvasImage(frozenCanvas, {
        hairItems,
        onComplete: () => {
          setAiEnhanceMessage(null)
          setIsCaptureCompleteModalOpen(true)
        },
        selectedHairId: displayHairId,
      })
      return
    }

    captureCompositedImage({
      videoRef: hasRemoteVideo ? remoteVideoRef : videoRef,
      wrapRef,
      hairItems,
      mirror: hasRemoteVideo ? false : RTC_STAGE_MIRRORED,
      onComplete: () => {
        setAiEnhanceMessage(null)
        setIsCaptureCompleteModalOpen(true)
      },
      selectedHairId: displayHairId,
    })
  }, [
    displayHairId,
    hairItems,
    hasRemoteVideo,
    isFrameFrozen,
    remoteVideoRef,
    videoRef,
  ])

  const handleAiEnhance = useCallback(async () => {
    const frozenCanvas = frozenFrameCanvasRef.current
    const wrap = wrapRef.current

    if (!frozenCanvas || !wrap) {
      setAiEnhanceMessage('캡처 이미지를 먼저 준비해 주세요.')
      return
    }

    try {
      const image = await canvasToBlob(frozenCanvas)
      const response = await aiUpgradeMutation.mutateAsync({
        image,
        deviceId: getOrCreateDeviceId(),
      })

      if (!response.resultImageUrl) {
        throw new Error('보정 이미지 URL이 없습니다.')
      }

      const didDraw = await drawImageUrlToCanvas({
        imageUrl: response.resultImageUrl,
        outputCanvas: frozenCanvas,
        width: wrap.clientWidth,
        height: wrap.clientHeight,
      })

      if (!didDraw) {
        throw new Error('보정 이미지를 화면에 표시하지 못했습니다.')
      }

      setIsCaptureCompleteModalOpen(false)
      setAiEnhanceMessage(null)
    } catch {
      setAiEnhanceMessage('AI 보정 요청에 실패했습니다.')
    }
  }, [aiUpgradeMutation])

  const handleTopLeftAction = useCallback(() => {
    if (isFrameFrozen) {
      setIsFrameFrozen(false)
      return
    }

    void router.navigate({ to: '/main' })
  }, [isFrameFrozen, router])

  const modalOpen = pendingHairId != null && pendingHairId > 0
  const hairItemsErrorOpen = hairItemsError != null
  const shouldShowGuideModal =
    isGuideModalOpen && !modalOpen && !hairItemsErrorOpen
  const hasRenderedPendingHair =
    modalOpen &&
    pendingHairId != null &&
    hairRtc.isRenderReady &&
    remoteDisplayReady
  const rtcApplyReady = hasRenderedPendingHair

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
    void (async () => {
      const me = await fetchMe().catch(() => null)
      if (me) {
        writeGuidePreference(me.userID, {
          dismissed: true,
        })
      }

      setIsGuideModalOpen(false)
    })()
  }, [writeGuidePreference])

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
            frozenFrameCanvasRef={frozenFrameCanvasRef}
            hasRemoteVideo={hasRemoteVideo}
            showFrozenFrame={isFrameFrozen}
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
            onFreezeChange={handleFreezeChange}
          />

          {shouldShowGuideModal ? (
            <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
              <GuideModal
                open={shouldShowGuideModal}
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

          {isCaptureCompleteModalOpen ? (
            <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/20 px-4">
              <CaptureCompleteModal
                open={isCaptureCompleteModalOpen}
                onClose={() => setIsCaptureCompleteModalOpen(false)}
                onFindDesigner={() => {}}
                onAiEnhance={() => {
                  void handleAiEnhance()
                }}
                aiEnhancePending={aiUpgradeMutation.isPending}
                aiEnhanceMessage={aiEnhanceMessage}
                scale={uiScale}
              />
            </div>
          ) : null}
        </div>
      </div>
    </main>
  )
}
