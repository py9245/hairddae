import { useRouter } from '@tanstack/react-router'
import { Settings, X } from 'lucide-react'
import type { RefObject } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { HairSelector } from '@/components/Camera/HairSelector'
import { Modal } from '@/components/Camera/Modal'
import type { HairRecommendResponse } from '@/lib/Camera/recommend'

type LandmarkPoint = {
  x: number
  y: number
  z: number
}

type HairItem = {
  id: number
  img: string
  thumb: string
  label: string
}

const HAIR_ITEMS: HairItem[] = [
  {
    id: 0,
    img: '',
    thumb: '',
    label: 'None',
  },
  {
    id: 1,
    img: '/hair/hair.png',
    thumb: '/hair/hair.png',
    label: 'Hair 1',
  },
]

function getVideoCoverLayout(
  containerWidth: number,
  containerHeight: number,
  videoWidth: number,
  videoHeight: number,
) {
  const scale = Math.max(
    containerWidth / videoWidth,
    containerHeight / videoHeight,
  )
  const drawWidth = videoWidth * scale
  const drawHeight = videoHeight * scale

  return {
    scale,
    offsetX: (containerWidth - drawWidth) / 2,
    offsetY: (containerHeight - drawHeight) / 2,
  }
}

export default function FaceLandmarksView({
  videoRef,
  canvasRef,
  overlayCanvasRef,
  selectedHairId,
  onHairApplied,
  recommendation,
  overlayImage,
  loading,
  error,
}: {
  videoRef: RefObject<HTMLVideoElement | null>
  canvasRef: RefObject<HTMLCanvasElement | null>
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>
  landmarks: LandmarkPoint[] | null
  selectedHairId: number
  onHairApplied: (hairId: number) => void
  recommendation: HairRecommendResponse | null
  overlayImage: HTMLImageElement | null
  loading: boolean
  error: string | null
}) {
  const router = useRouter()
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const [pendingHairId, setPendingHairId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const displayHairId = pendingHairId ?? selectedHairId

  const pendingHair = useMemo(() => {
    if (pendingHairId == null) return null
    return HAIR_ITEMS.find((item) => item.id === pendingHairId) ?? null
  }, [pendingHairId])

  const handleHairSelect = useCallback(
    (nextId: number) => {
      if (modalOpen) return
      if (nextId === selectedHairId) return

      setPendingHairId(nextId)
      setModalOpen(true)
    },
    [modalOpen, selectedHairId],
  )

  const handleModalComplete = useCallback(() => {
    if (pendingHairId != null) {
      onHairApplied(pendingHairId)
    }
    setPendingHairId(null)
    setModalOpen(false)
  }, [onHairApplied, pendingHairId])

  const handleClose = useCallback(() => {
    void router.navigate({ to: '/main' })
  }, [router])

  useEffect(() => {
    const canvas = overlayCanvasRef.current
    const wrap = wrapRef.current
    const video = videoRef.current
    const bbox = recommendation?.asset.hairRgbaBBox

    if (!canvas || !wrap) {
      return
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) {
      return
    }

    const width = wrap.clientWidth
    const height = wrap.clientHeight

    if (canvas.width !== width) {
      canvas.width = width
    }
    if (canvas.height !== height) {
      canvas.height = height
    }

    ctx.clearRect(0, 0, width, height)

    if (!overlayImage || !bbox || !video?.videoWidth || !video.videoHeight) {
      return
    }

    const { scale, offsetX, offsetY } = getVideoCoverLayout(
      width,
      height,
      video.videoWidth,
      video.videoHeight,
    )

    ctx.save()
    ctx.globalAlpha = 0.96
    ctx.drawImage(
      overlayImage,
      bbox.x * scale + offsetX,
      bbox.y * scale + offsetY,
      bbox.w * scale,
      bbox.h * scale,
    )
    ctx.restore()
  }, [overlayCanvasRef, overlayImage, recommendation, videoRef])

  return (
    <div className="grid h-[100dvh] w-full place-items-center overflow-hidden bg-neutral-100">
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

        <div className="absolute inset-x-0 top-0 z-20 flex items-center justify-between px-4 pb-4 pt-5">
          <button
            type="button"
            aria-label="Go to main"
            onClick={handleClose}
            className="flex h-11 w-11 items-center justify-center text-white/85 transition hover:text-white"
          >
            <X className="h-10 w-10" />
          </button>

          <button
            type="button"
            aria-label="Open settings"
            className="flex h-11 w-11 items-center justify-center text-white/85 transition hover:text-white"
          >
            <Settings className="h-10 w-10" />
          </button>
        </div>

        <div className="absolute top-2 left-2 z-20 rounded bg-black/60 px-2 py-1 text-xs text-white">
          {loading ? 'Loading recommendation' : 'Recommendation ready'}
        </div>

        {error && (
          <div className="absolute top-10 left-2 z-20 rounded bg-red-600/80 px-2 py-1 text-xs text-white">
            {error}
          </div>
        )}

        <HairSelector
          items={HAIR_ITEMS}
          selectedId={displayHairId}
          onSelect={handleHairSelect}
        />
      </div>

      <Modal
        open={modalOpen}
        targetLabel={pendingHair?.label}
        onComplete={handleModalComplete}
      />
    </div>
  )
}
