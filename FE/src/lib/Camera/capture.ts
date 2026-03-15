import type { RefObject } from 'react'
import type { HairItem } from '@/lib/Camera/HairItem'
import { getVideoCoverLayout } from '@/lib/Camera/layout'

type CaptureCompositedImageArgs = {
  videoRef: RefObject<HTMLVideoElement | null>
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>
  wrapRef: RefObject<HTMLDivElement | null>
  hairItems: HairItem[]
  selectedHairId: number
}

export function captureCompositedImage({
  videoRef,
  overlayCanvasRef,
  wrapRef,
  hairItems,
  selectedHairId,
}: CaptureCompositedImageArgs) {
  const video = videoRef.current
  const overlay = overlayCanvasRef.current
  const wrap = wrapRef.current

  if (!wrap || !video || video.videoWidth === 0 || video.videoHeight === 0) {
    return
  }

  const width = wrap.clientWidth
  const height = wrap.clientHeight

  const out = document.createElement('canvas')
  out.width = width
  out.height = height

  const ctx = out.getContext('2d')
  if (!ctx) return

  ctx.save()
  ctx.translate(width, 0)
  ctx.scale(-1, 1)

  const { offsetX, offsetY, scale } = getVideoCoverLayout(
    width,
    height,
    video.videoWidth,
    video.videoHeight,
  )

  const drawWidth = video.videoWidth * scale
  const drawHeight = video.videoHeight * scale

  ctx.drawImage(
    video,
    0,
    0,
    video.videoWidth,
    video.videoHeight,
    offsetX,
    offsetY,
    drawWidth,
    drawHeight,
  )
  ctx.restore()

  if (overlay?.width && overlay?.height) {
    ctx.save()
    ctx.translate(width, 0)
    ctx.scale(-1, 1)
    ctx.drawImage(overlay, 0, 0, width, height)
    ctx.restore()
  }

  out.toBlob((blob) => {
    if (!blob) return

    const url = URL.createObjectURL(blob)
    const currentHair = hairItems.find((item) => item.id === selectedHairId)
    const nameBase = (currentHair?.label ?? 'capture').replace(/\s+/g, '_')
    const ts = new Date().toISOString().replace(/[:.]/g, '-')

    const a = document.createElement('a')
    a.href = url
    a.download = `${nameBase}-${ts}.png`
    document.body.appendChild(a)
    a.click()
    a.remove()

    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }, 'image/png')
}
