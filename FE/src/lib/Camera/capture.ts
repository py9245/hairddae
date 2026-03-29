import type { RefObject } from 'react'
import type { HairItem } from '@/lib/Camera/HairItem'
import { getVideoCoverLayout } from '@/lib/Camera/layout'

type CaptureCompositedImageArgs = {
  videoRef: RefObject<HTMLVideoElement | null>
  wrapRef: RefObject<HTMLDivElement | null>
  hairItems: HairItem[]
  mirror: boolean
  selectedHairId: number
}

export function captureCompositedImage({
  videoRef,
  wrapRef,
  hairItems,
  mirror,
  selectedHairId,
}: CaptureCompositedImageArgs) {
  const video = videoRef.current
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

  if (mirror) {
    ctx.save()
    ctx.translate(width, 0)
    ctx.scale(-1, 1)
  }

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
  if (mirror) {
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
