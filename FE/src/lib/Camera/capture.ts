import type { RefObject } from 'react'
import type { HairItem } from '@/lib/Camera/HairItem'
import { getVideoCoverLayout } from '@/lib/Camera/layout'

type CaptureSource = HTMLCanvasElement | HTMLImageElement | HTMLVideoElement

type CaptureCompositedImageArgs = {
  videoRef: RefObject<HTMLVideoElement | null>
  wrapRef: RefObject<HTMLDivElement | null>
  hairItems: HairItem[]
  mirror: boolean
  selectedHairId: number
}

type DownloadCaptureArgs = {
  hairItems: HairItem[]
  selectedHairId: number
  onComplete?: () => void
}

type DrawCompositedSourceToCanvasArgs = {
  source: CaptureSource
  outputCanvas: HTMLCanvasElement
  width: number
  height: number
  mirror: boolean
}

export async function drawImageUrlToCanvas({
  imageUrl,
  outputCanvas,
  width,
  height,
}: {
  imageUrl: string
  outputCanvas: HTMLCanvasElement
  width: number
  height: number
}) {
  const image = new Image()
  image.decoding = 'async'
  image.crossOrigin = 'anonymous'

  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve()
    image.onerror = () =>
      reject(new Error('보정 이미지를 불러오지 못했습니다.'))
    image.src = imageUrl
  })

  return drawCompositedSourceToCanvas({
    source: image,
    outputCanvas,
    width,
    height,
    mirror: false,
  })
}

function getCaptureSourceSize(source: CaptureSource) {
  if (source instanceof HTMLVideoElement) {
    return {
      width: source.videoWidth,
      height: source.videoHeight,
    }
  }

  if (source instanceof HTMLImageElement) {
    return {
      width: source.naturalWidth,
      height: source.naturalHeight,
    }
  }

  return {
    width: source.width,
    height: source.height,
  }
}

function downloadCaptureBlob(
  blob: Blob,
  { hairItems, selectedHairId, onComplete }: DownloadCaptureArgs,
) {
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
  onComplete?.()

  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function drawCompositedSourceToCanvas({
  source,
  outputCanvas,
  width,
  height,
  mirror,
}: DrawCompositedSourceToCanvasArgs) {
  const ctx = outputCanvas.getContext('2d')
  if (!ctx || width <= 0 || height <= 0) {
    return false
  }

  const { width: sourceWidth, height: sourceHeight } =
    getCaptureSourceSize(source)
  if (sourceWidth <= 0 || sourceHeight <= 0) {
    return false
  }

  if (outputCanvas.width !== width) {
    outputCanvas.width = width
  }
  if (outputCanvas.height !== height) {
    outputCanvas.height = height
  }

  ctx.clearRect(0, 0, width, height)

  if (mirror) {
    ctx.save()
    ctx.translate(width, 0)
    ctx.scale(-1, 1)
  }

  const { offsetX, offsetY, scale } = getVideoCoverLayout(
    width,
    height,
    sourceWidth,
    sourceHeight,
  )

  const drawWidth = sourceWidth * scale
  const drawHeight = sourceHeight * scale

  ctx.drawImage(
    source,
    0,
    0,
    sourceWidth,
    sourceHeight,
    offsetX,
    offsetY,
    drawWidth,
    drawHeight,
  )
  if (mirror) {
    ctx.restore()
  }

  return true
}

export function downloadCanvasImage(
  canvas: HTMLCanvasElement,
  { hairItems, selectedHairId, onComplete }: DownloadCaptureArgs,
) {
  canvas.toBlob((blob) => {
    if (!blob) return
    downloadCaptureBlob(blob, { hairItems, selectedHairId, onComplete })
  }, 'image/png')
}

export function canvasToBlob(
  canvas: HTMLCanvasElement,
  type = 'image/png',
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('캡처 이미지를 생성하지 못했습니다.'))
        return
      }

      resolve(blob)
    }, type)
  })
}

export function captureCompositedImage({
  videoRef,
  wrapRef,
  hairItems,
  mirror,
  selectedHairId,
  onComplete,
}: CaptureCompositedImageArgs & { onComplete?: () => void }) {
  const video = videoRef.current
  const wrap = wrapRef.current

  if (!wrap || !video || video.videoWidth === 0 || video.videoHeight === 0) {
    return
  }

  const out = document.createElement('canvas')
  const didDraw = drawCompositedSourceToCanvas({
    source: video,
    outputCanvas: out,
    width: wrap.clientWidth,
    height: wrap.clientHeight,
    mirror,
  })
  if (!didDraw) {
    return
  }

  out.toBlob((blob) => {
    if (!blob) return
    downloadCaptureBlob(blob, { hairItems, selectedHairId, onComplete })
  }, 'image/png')
}
