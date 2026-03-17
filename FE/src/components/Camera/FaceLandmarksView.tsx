import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useRouter } from '@tanstack/react-router'
import { Settings, X } from 'lucide-react'
import { type RefObject, useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { HairSelector } from '@/components/Camera/HairSelector'
import { ApplyStyleModal } from '@/components/Camera/Modal'
import { useHairInferenceSession } from '@/hooks/Camera/useHairInferenceSession'
import { useHairRtcSession } from '@/hooks/Camera/useHairRtcSession'
import { useHairOverlayCanvas } from '@/hooks/Camera/useHairOverlayCanvas'
import { captureCompositedImage } from '@/lib/Camera/capture'
import { fetchHairItems, HAIR_ITEMS, type HairItem } from '@/lib/Camera/HairItem'

type Pose = {
  yaw: number
  pitch: number
  roll: number
}

const REMOTE_DISPLAY_SETTLE_MS = 40

type FaceLandmarksViewProps = {
  stream: MediaStream | null
  transport: 'ws' | 'rtc'
  videoRef: RefObject<HTMLVideoElement | null>
  canvasRef: RefObject<HTMLCanvasElement | null>
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>
  pose: Pose | null
  landmarks: NormalizedLandmark[] | null
}

export default function FaceLandmarksView({
  stream,
  transport,
  videoRef,
  canvasRef,
  overlayCanvasRef,
  pose,
  landmarks,
}: FaceLandmarksViewProps) {
  const router = useRouter()
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null)

  const [selectedHairId, setSelectedHairId] = useState(0)
  const [pendingHairId, setPendingHairId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [hairItems, setHairItems] = useState<HairItem[]>(HAIR_ITEMS)
  const [remoteVideoReady, setRemoteVideoReady] = useState(false)
  const [remoteDisplayReady, setRemoteDisplayReady] = useState(false)

  const displayHairId = pendingHairId ?? selectedHairId
  const quickHairItems = useMemo(() => {
    const candidates = hairItems.filter((item) => item.id > 0).slice(0, 4)
    if (candidates.length > 0) {
      return candidates
    }
    return [
      {
        id: 1,
        img: '/hair/hair.png',
        thumb: '/hair/hair.png',
        label: 'Hair 1',
      },
    ]
  }, [hairItems])

  const hairInference = useHairInferenceSession({
    enabled: transport === 'ws' && displayHairId > 0,
    hairId: displayHairId,
    pose,
    landmarks,
    videoRef,
  })

  const hairRtc = useHairRtcSession({
    enabled: transport === 'rtc' && displayHairId > 0,
    hairId: displayHairId,
    stream,
  })

  const overlayMetrics = useHairOverlayCanvas({
    canvasRef: overlayCanvasRef,
    videoRef,
    landmarks,
    asset: transport === 'ws' ? hairInference.asset : null,
  })

  const activeRemoteStream = transport === 'rtc' ? hairRtc.remoteStream : null
  const hasRemoteVideo =
    transport === 'rtc' && remoteDisplayReady

  const activeAsset = transport === 'rtc' ? hairRtc.asset : hairInference.asset

  const activeMetrics =
    transport === 'rtc' ? hairRtc.metrics : hairInference.metrics

  const activeError = transport === 'rtc' ? hairRtc.error : hairInference.error
  const activeConnected =
    transport === 'rtc' ? hairRtc.isConnected : hairInference.isConnected

  useEffect(() => {
    const remoteVideo = remoteVideoRef.current
    if (!remoteVideo) {
      return
    }

    setRemoteVideoReady(false)
    remoteVideo.srcObject = activeRemoteStream
    if (!activeRemoteStream) {
      return () => {
        remoteVideo.srcObject = null
      }
    }

    const markReady = () => {
      if (remoteVideo.videoWidth <= 0 || remoteVideo.videoHeight <= 0) {
        return
      }
      setRemoteVideoReady(true)
    }

    const markWaiting = () => {
      setRemoteVideoReady(false)
    }

    remoteVideo.addEventListener('loadedmetadata', markReady)
    remoteVideo.addEventListener('loadeddata', markReady)
    remoteVideo.addEventListener('playing', markReady)
    remoteVideo.addEventListener('resize', markReady)
    remoteVideo.addEventListener('emptied', markWaiting)
    remoteVideo.addEventListener('pause', markWaiting)

    if (activeRemoteStream.getVideoTracks().length > 0) {
      void remoteVideo.play().catch(() => {})
    }

    return () => {
      remoteVideo.removeEventListener('loadedmetadata', markReady)
      remoteVideo.removeEventListener('loadeddata', markReady)
      remoteVideo.removeEventListener('playing', markReady)
      remoteVideo.removeEventListener('resize', markReady)
      remoteVideo.removeEventListener('emptied', markWaiting)
      remoteVideo.removeEventListener('pause', markWaiting)
      setRemoteVideoReady(false)
      remoteVideo.srcObject = null
    }
  }, [activeRemoteStream])

  useEffect(() => {
    if (transport !== 'rtc') {
      setRemoteDisplayReady(false)
      return
    }
    if (!remoteVideoReady || !hairRtc.isRenderReady) {
      setRemoteDisplayReady(false)
      return
    }

    const timeoutId = window.setTimeout(() => {
      setRemoteDisplayReady(true)
    }, REMOTE_DISPLAY_SETTLE_MS)

    return () => {
      window.clearTimeout(timeoutId)
      setRemoteDisplayReady(false)
    }
  }, [hairRtc.isRenderReady, remoteVideoReady, transport])

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

  useEffect(() => {
    const abortController = new AbortController()

    void fetchHairItems(abortController.signal)
      .then((items) => {
        setHairItems(items)
      })
      .catch((error) => {
        if (abortController.signal.aborted) {
          return
        }
        console.warn('hair list load failed:', error)
      })

    return () => {
      abortController.abort()
    }
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
      videoRef: hasRemoteVideo ? remoteVideoRef : videoRef,
      overlayCanvasRef,
      wrapRef,
      hairItems,
      selectedHairId: displayHairId,
    })
  }, [displayHairId, hairItems, hasRemoteVideo, overlayCanvasRef, videoRef])

  const handleQuickHairSelect = useCallback((hairId: number) => {
    setPendingHairId(null)
    setModalOpen(false)
    setSelectedHairId(hairId)
  }, [])

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
          className={
            hasRemoteVideo
              ? 'absolute inset-0 h-full w-full object-cover -scale-x-100 opacity-0'
              : 'block h-full w-full object-cover -scale-x-100'
          }
        />

        <video
          ref={remoteVideoRef}
          autoPlay
          playsInline
          muted
          className={
            hasRemoteVideo
              ? 'absolute inset-0 z-10 h-full w-full object-cover -scale-x-100'
              : 'hidden'
          }
        />

        <canvas
          ref={canvasRef}
          className="pointer-events-none absolute inset-0 hidden h-full w-full -scale-x-100"
        />

        <canvas
          ref={overlayCanvasRef}
          className={
            transport === 'ws'
              ? 'pointer-events-none absolute inset-0 z-10 h-full w-full -scale-x-100'
              : 'hidden'
          }
        />

        <div className="absolute inset-x-0 top-0 z-20 flex items-center justify-between px-4 pt-5">
          <button type="button" onClick={handleClose}>
            <X className="h-10 w-10 text-white" />
          </button>

          <Settings className="h-10 w-10 text-white" />
        </div>

        <div className="absolute top-2 left-2 z-20 rounded bg-black/60 px-2 py-1 text-xs text-white">
          {activeError
            ? activeError
            : activeConnected
              ? transport === 'rtc'
                ? 'RTC 연결됨'
                : '소켓 연결됨'
              : displayHairId > 0
                ? transport === 'rtc'
                  ? 'RTC 연결 중'
                  : '소켓 연결 중'
                : '헤어 선택 전'}
        </div>

        <div className="absolute top-10 left-2 z-20 rounded bg-black/60 px-2 py-1 text-[10px] text-white">
          {activeAsset
            ? `asset ${activeAsset.poseKey}`
            : '준비 완료'}
        </div>

        <div className="absolute top-[4.5rem] left-2 z-20 rounded bg-black/60 px-2 py-1 text-[10px] text-white">
          {transport === 'rtc'
            ? `rtc ${hairRtc.connectionState} / rtt ${
                activeMetrics.inferenceRttMs == null
                  ? '-'
                  : `${Math.round(activeMetrics.inferenceRttMs)}ms`
              }`
            : `draw ${
                overlayMetrics.drawFps == null
                  ? '-'
                  : overlayMetrics.drawFps.toFixed(1)
              } fps / rtt ${
                activeMetrics.inferenceRttMs == null
                  ? '-'
                  : `${Math.round(activeMetrics.inferenceRttMs)}ms`
              }`}
        </div>

        <div className="absolute top-[6rem] left-2 z-20 rounded bg-black/60 px-2 py-1 text-[10px] text-white">
          {transport === 'rtc'
            ? `proc ${
                activeMetrics.processedFps == null
                  ? '-'
                  : activeMetrics.processedFps.toFixed(1)
              } fps / remote ${
                hasRemoteVideo
                  ? 'ready'
                  : remoteVideoReady && hairRtc.isRenderReady
                    ? 'settling'
                    : remoteVideoReady
                    ? 'warming'
                    : 'waiting'
              }`
            : `proc ${
                activeMetrics.processedFps == null
                  ? '-'
                  : activeMetrics.processedFps.toFixed(1)
              } fps / bundle ${
                overlayMetrics.bundleReady
                  ? overlayMetrics.bundleLoadMs == null
                    ? 'ready'
                    : `${Math.round(overlayMetrics.bundleLoadMs)}ms`
                  : 'loading'
              }`}
        </div>

        <div className="absolute top-[8rem] right-2 z-20 flex flex-col gap-2">
          <button
            type="button"
            onClick={() => handleQuickHairSelect(0)}
            className={`rounded px-3 py-1 text-xs ${
              selectedHairId === 0
                ? 'bg-pink-500 text-white'
                : 'bg-black/60 text-white'
            }`}
          >
            해제
          </button>
          {quickHairItems.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => handleQuickHairSelect(item.id)}
              className={`rounded px-3 py-1 text-xs ${
                selectedHairId === item.id
                  ? 'bg-pink-500 text-white'
                  : 'bg-black/60 text-white'
              }`}
            >
              hair {item.id}
            </button>
          ))}
        </div>

        <HairSelector
          items={hairItems}
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
