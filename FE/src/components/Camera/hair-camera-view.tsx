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
}

type CameraTrackInfo = {
  width: number | null
  height: number | null
  frameRate: number | null
}

function resolveCameraErrorMessage(error: unknown) {
  if (error instanceof DOMException) {
    if (error.name === 'NotAllowedError') {
      return '카메라 권한이 필요합니다.'
    }
    if (error.name === 'NotFoundError') {
      return '사용 가능한 전면 카메라를 찾지 못했습니다.'
    }
    if (error.name === 'NotReadableError') {
      return '카메라가 다른 앱에서 사용 중입니다.'
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message
  }

  return '카메라를 시작하지 못했습니다.'
}

function formatResolution(width: number | null, height: number | null) {
  if (!width || !height) {
    return '-'
  }

  return `${width}x${height}`
}

function formatFps(value: number | null) {
  if (value == null || !Number.isFinite(value)) {
    return '-'
  }

  return `${value.toFixed(1)}fps`
}

function formatMs(value: number | null) {
  if (value == null || !Number.isFinite(value)) {
    return '-'
  }

  return `${Math.round(value)}ms`
}

function formatBitrate(value: number | null) {
  if (value == null || !Number.isFinite(value) || value <= 0) {
    return '-'
  }

  return `${Math.round(value)}kbps`
}

function StatusChip({
  tone = 'neutral',
  children,
}: {
  tone?: 'neutral' | 'success' | 'error'
  children: React.ReactNode
}) {
  const toneClassName =
    tone === 'error'
      ? 'border-rose-300/50 bg-rose-500/75 text-white'
      : tone === 'success'
        ? 'border-emerald-300/50 bg-emerald-500/75 text-white'
        : 'border-white/20 bg-black/55 text-white'

  return (
    <div
      className={`absolute left-4 top-22 z-20 rounded-full border px-3 py-1.5 text-xs font-medium tracking-[0.01em] backdrop-blur ${toneClassName}`}
    >
      {children}
    </div>
  )
}

function MetricsPanel({
  camera,
  remoteWidth,
  remoteHeight,
  hasRemoteVideo,
  metrics,
}: {
  camera: CameraTrackInfo
  remoteWidth: number | null
  remoteHeight: number | null
  hasRemoteVideo: boolean
  metrics: ReturnType<typeof useHairRtcSession>['metrics']
}) {
  return (
    <div className="pointer-events-none absolute right-4 top-22 z-20 w-[min(calc(100%-2rem),240px)] rounded-2xl border border-white/12 bg-black/55 px-3 py-3 text-[11px] leading-4 text-white shadow-[0_20px_60px_rgba(15,23,42,0.32)] backdrop-blur">
      <div className="flex items-center justify-between gap-2">
        <p className="font-semibold tracking-[0.08em] text-slate-100">
          RTC Monitor
        </p>
        <span className="text-slate-300">
          {hasRemoteVideo ? 'remote live' : 'warming'}
        </span>
      </div>

      <div className="mt-2 grid grid-cols-[56px_1fr] gap-x-3 gap-y-1.5 text-slate-200">
        <span className="text-slate-400">원본</span>
        <span>
          {formatResolution(camera.width, camera.height)} /{' '}
          {formatFps(camera.frameRate)}
        </span>

        <span className="text-slate-400">업링크</span>
        <span>
          {formatResolution(
            metrics.senderFrameWidth,
            metrics.senderFrameHeight,
          )}{' '}
          / {formatFps(metrics.senderFps)}
        </span>

        <span className="text-slate-400">스테이지</span>
        <span>{`${RTC_STAGE_WIDTH}x${RTC_STAGE_HEIGHT} / ${RTC_STAGE_FPS}fps`}</span>

        <span className="text-slate-400">리모트</span>
        <span>
          {hasRemoteVideo
            ? `${formatResolution(remoteWidth, remoteHeight)} / ${formatFps(metrics.receiverFps)}`
            : '대기 중'}
        </span>

        <span className="text-slate-400">비트율</span>
        <span>{formatBitrate(metrics.senderBitrateKbps)}</span>

        <span className="text-slate-400">RTT</span>
        <span>
          {formatMs(metrics.roundTripTimeMs ?? metrics.heartbeatRttMs)}
        </span>

        <span className="text-slate-400">Infer</span>
        <span>{formatMs(metrics.inferMs)}</span>

        <span className="text-slate-400">Encode</span>
        <span>{formatMs(metrics.encodeMs)}</span>

        <span className="text-slate-400">E2E</span>
        <span>{formatMs(metrics.e2eEstimateMs)}</span>

        <span className="text-slate-400">Queue</span>
        <span>
          {metrics.queueDepth} / drop {metrics.droppedPendingCount}
          {metrics.packetsLost != null ? ` / loss ${metrics.packetsLost}` : ''}
        </span>
      </div>
    </div>
  )
}

export function HairCameraView({
  videoRef,
  cameraStream,
  cameraReady,
  cameraError,
}: HairCameraViewProps) {
  const router = useRouter()
  const wrapRef = useRef<HTMLDivElement | null>(null)

  const [selectedHairId, setSelectedHairId] = useState(0)
  const [pendingHairId, setPendingHairId] = useState<number | null>(null)
  const [hairItems, setHairItems] = useState<HairItem[]>(HAIR_ITEMS)
  const [isHairItemsLoading, setIsHairItemsLoading] = useState(true)
  const [isFrameFrozen, setIsFrameFrozen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [stageMirrored, setStageMirrored] = useState(RTC_STAGE_MIRRORED)
  const [uiScale, setUiScale] = useState(1)
  const [cameraTrackInfo, setCameraTrackInfo] = useState<CameraTrackInfo>({
    width: null,
    height: null,
    frameRate: null,
  })

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

  const {
    remoteVideoRef,
    remoteDisplayReady,
    remoteVideoReady,
    remoteVideoSize,
    hasRemoteVideo,
  } = useHairRtcDisplay({
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
    const track = cameraStream?.getVideoTracks()[0]
    if (!track) {
      setCameraTrackInfo({
        width: null,
        height: null,
        frameRate: null,
      })
      return
    }

    const settings = track.getSettings()
    setCameraTrackInfo({
      width: typeof settings.width === 'number' ? settings.width : null,
      height: typeof settings.height === 'number' ? settings.height : null,
      frameRate:
        typeof settings.frameRate === 'number' ? settings.frameRate : null,
    })
  }, [cameraStream])

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

  const handleHairSelect = useCallback((hairId: number) => {
    setIsFrameFrozen(false)
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
      mirror: stageMirrored,
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

  const cameraErrorMessage = cameraError
    ? resolveCameraErrorMessage(cameraError)
    : null

  const modalOpen = pendingHairId != null
  const rtcApplyReady =
    modalOpen &&
    pendingHairId != null &&
    hairRtc.appliedHairId === pendingHairId &&
    hairRtc.isConnected &&
    !hairRtc.error

  const statusMessage = cameraErrorMessage
    ? cameraErrorMessage
    : !cameraReady
      ? '카메라 준비 중'
      : displayHairId <= 0
        ? '스타일 선택 필요'
        : hairRtc.error
          ? hairRtc.error
          : !stageStream
            ? '업링크 준비 중'
            : !hairRtc.isConnected
              ? 'RTC 연결 중'
              : !remoteVideoReady || !remoteDisplayReady
                ? '처리 영상 준비 중'
                : hairRtc.appliedHairId === displayHairId
                  ? '실시간 적용 중'
                  : '스타일 반영 중'

  const statusTone: 'neutral' | 'success' | 'error' = cameraErrorMessage
    ? 'error'
    : hairRtc.error
      ? 'error'
      : displayHairId > 0 && remoteDisplayReady && hairRtc.isConnected
        ? 'success'
        : 'neutral'

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
            mirrored={stageMirrored}
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

          <StatusChip tone={statusTone}>{statusMessage}</StatusChip>

          <MetricsPanel
            camera={cameraTrackInfo}
            remoteWidth={remoteVideoSize?.width ?? null}
            remoteHeight={remoteVideoSize?.height ?? null}
            hasRemoteVideo={hasRemoteVideo}
            metrics={hairRtc.metrics}
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
