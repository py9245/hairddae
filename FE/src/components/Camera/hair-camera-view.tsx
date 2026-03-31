import { useMutation } from '@tanstack/react-query'
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
import { fetchMe } from '@/lib/auth'
import { postAiUpgrade } from '@/lib/Camera/ai-upgrade'
import {
  canvasToBlob,
  captureCompositedImage,
  downloadCanvasImage,
  drawCompositedSourceToCanvas,
  drawImageUrlToCanvas,
} from '@/lib/Camera/capture'
import { postGetDesigner } from '@/lib/Camera/designer'
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
  const [aiEnhanceMessage, setAiEnhanceMessage] = useState<string | null>(null)
  const [designerLocationMessage, setDesignerLocationMessage] = useState<
    string | null
  >(null)
  const [captureToastVisible, setCaptureToastVisible] = useState(false)
  const [isGuideModalOpen, setIsGuideModalOpen] = useState(false)
  const [isFrameFrozen, setIsFrameFrozen] = useState(false)
  const [uiScale, setUiScale] = useState(1)

  const aiUpgradeMutation = useMutation({
    mutationFn: postAiUpgrade,
  })
  const designerMutation = useMutation({
    mutationFn: postGetDesigner,
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
    if (!captureToastVisible) {
      return
    }

    const timerId = window.setTimeout(() => {
      setCaptureToastVisible(false)
    }, 1800)

    return () => {
      window.clearTimeout(timerId)
    }
  }, [captureToastVisible])

  useEffect(() => {
    if (!aiEnhanceMessage || aiUpgradeMutation.isPending) {
      return
    }

    const timerId = window.setTimeout(() => {
      setAiEnhanceMessage(null)
    }, 2200)

    return () => {
      window.clearTimeout(timerId)
    }
  }, [aiEnhanceMessage, aiUpgradeMutation.isPending])

  useEffect(() => {
    if (!designerLocationMessage || designerMutation.isPending) {
      return
    }

    const timerId = window.setTimeout(() => {
      setDesignerLocationMessage(null)
    }, 2500)

    return () => {
      window.clearTimeout(timerId)
    }
  }, [designerLocationMessage, designerMutation.isPending])

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
            title: '?ㅼ뼱 ?ㅽ???紐⑸줉??遺덈윭?????놁뼱??',
            description: [
              '?꾩옱 ?곸슜 媛?ν븳 ?ㅼ뼱 ?ㅽ????뺣낫媛 ?놁뼱??',
              '?ㅼ쓬 ?붾㈃?먯꽌 ?곸슜?섍린瑜??좏깮??二쇱꽭??',
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
          title: '?ㅼ뼱 ?ㅽ???紐⑸줉??遺덈윭?????놁뼱??',
          description: ['?ㅽ듃?뚰겕 ?곹깭瑜??뺤씤?????ㅼ떆 ?쒕룄??二쇱꽭??'],
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
          setCaptureToastVisible(true)
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
        setCaptureToastVisible(true)
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
      setAiEnhanceMessage('罹≪쿂 ?대?吏瑜?癒쇱? 以鍮꾪빐 二쇱꽭??')
      return
    }

    try {
      const image = await canvasToBlob(frozenCanvas)
      const response = await aiUpgradeMutation.mutateAsync({
        image,
        deviceId: getOrCreateDeviceId(),
      })

      if (!response.resultImageUrl) {
        throw new Error('蹂댁젙 ?대?吏 URL???놁뒿?덈떎.')
      }

      const didDraw = await drawImageUrlToCanvas({
        imageUrl: response.resultImageUrl,
        outputCanvas: frozenCanvas,
        width: wrap.clientWidth,
        height: wrap.clientHeight,
      })

      if (!didDraw) {
        throw new Error('蹂댁젙 ?대?吏瑜??붾㈃???쒖떆?섏? 紐삵뻽?듬땲??')
      }

      setAiEnhanceMessage(null)
    } catch {
      setAiEnhanceMessage('AI 蹂댁젙 ?붿껌???ㅽ뙣?덉뒿?덈떎.')
    }
  }, [aiUpgradeMutation])

  const handleFindDesigner = useCallback(() => {
    if (displayHairId <= 0) {
      setDesignerLocationMessage('적용된 헤어 정보를 찾을 수 없습니다.')
      return
    }

    if (typeof window === 'undefined' || !navigator.geolocation) {
      setDesignerLocationMessage('현재 위치를 지원하지 않는 환경입니다.')
      return
    }

    setDesignerLocationMessage('현재 위치를 확인하고 있습니다...')

    navigator.geolocation.getCurrentPosition(
      (position) => {
        void (async () => {
          try {
            const { latitude, longitude } = position.coords
            const response = await designerMutation.mutateAsync({
              latitude,
              longitude,
              hairId: displayHairId,
            })

            setDesignerLocationMessage(response.message)
          } catch {
            setDesignerLocationMessage('디자이너 목록을 가져오지 못했습니다.')
          }
        })()
      },
      () => {
        setDesignerLocationMessage('현재 위치를 가져오지 못했습니다.')
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      },
    )
  }, [designerMutation, displayHairId])

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
                aria-label={isFrameFrozen ? '罹≪쿂 痍⑥냼' : '?リ린'}
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
            aiEnhancePending={
              aiUpgradeMutation.isPending || designerMutation.isPending
            }
            onSelect={handleHairSelect}
            onCapture={handleCapture}
            onFreezeChange={handleFreezeChange}
            onFindDesigner={handleFindDesigner}
            onAiEnhance={() => {
              void handleAiEnhance()
            }}
          />

          {captureToastVisible ? (
            <div className="pointer-events-none absolute left-1/2 top-24 z-40 -translate-x-1/2">
              <div className="rounded-full bg-white px-6 py-3 text-base font-bold text-primary-300 shadow-[0_8px_24px_rgba(15,23,42,0.16)]">
                ??μ씠 ?꾨즺?섏뿀?듬땲??
              </div>
            </div>
          ) : null}

          {aiEnhanceMessage ? (
            <div className="pointer-events-none absolute left-1/2 top-40 z-40 -translate-x-1/2">
              <div className="rounded-full bg-white px-6 py-3 text-base font-bold text-primary-300 shadow-[0_8px_24px_rgba(15,23,42,0.16)]">
                {aiEnhanceMessage}
              </div>
            </div>
          ) : null}

          {designerLocationMessage ? (
            <div className="pointer-events-none absolute left-1/2 top-56 z-40 -translate-x-1/2">
              <div className="rounded-full bg-white px-6 py-3 text-base font-bold text-primary-300 shadow-[0_8px_24px_rgba(15,23,42,0.16)]">
                {designerLocationMessage}
              </div>
            </div>
          ) : null}

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
        </div>
      </div>
    </main>
  )
}
