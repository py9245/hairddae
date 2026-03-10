import type { NormalizedLandmark } from '@mediapipe/tasks-vision'

export function syncCanvasSize(canvas: HTMLCanvasElement) {
  const rect = canvas.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1

  const nextW = Math.round(rect.width * dpr)
  const nextH = Math.round(rect.height * dpr)

  if (canvas.width !== nextW) canvas.width = nextW
  if (canvas.height !== nextH) canvas.height = nextH
}

function getCoverRect(
  videoW: number,
  videoH: number,
  canvasW: number,
  canvasH: number,
) {
  const scale = Math.max(canvasW / videoW, canvasH / videoH)
  const drawW = videoW * scale
  const drawH = videoH * scale
  const ox = (canvasW - drawW) / 2
  const oy = (canvasH - drawH) / 2

  return { scale, drawW, drawH, ox, oy }
}

function lmToCoverXY(
  lm: NormalizedLandmark,
  videoW: number,
  videoH: number,
  canvasW: number,
  canvasH: number,
) {
  const { drawW, drawH, ox, oy } = getCoverRect(
    videoW,
    videoH,
    canvasW,
    canvasH,
  )

  return {
    x: ox + lm.x * drawW,
    y: oy + lm.y * drawH,
  }
}

export function drawLandmarksCover(
  canvas: HTMLCanvasElement,
  lms: NormalizedLandmark[],
  videoW: number,
  videoH: number,
) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const W = canvas.width
  const H = canvas.height

  ctx.clearRect(0, 0, W, H)
  if (!lms.length) return

  ctx.save()
  ctx.fillStyle = '#8BFF5A'

  for (const lm of lms) {
    const { x, y } = lmToCoverXY(lm, videoW, videoH, W, H)

    ctx.beginPath()
    ctx.arc(x, y, 2.5 * (window.devicePixelRatio || 1), 0, Math.PI * 2)
    ctx.fill()
  }

  ctx.restore()
}

export function drawRedPointsCover(
  canvas: HTMLCanvasElement,
  lms: NormalizedLandmark[],
  idxs: number[],
  videoW: number,
  videoH: number,
) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const W = canvas.width
  const H = canvas.height

  ctx.save()
  ctx.fillStyle = 'red'

  for (const i of idxs) {
    const p = lms[i]
    if (!p) continue

    const { x, y } = lmToCoverXY(p, videoW, videoH, W, H)

    ctx.beginPath()
    ctx.arc(x, y, 5 * (window.devicePixelRatio || 1), 0, Math.PI * 2)
    ctx.fill()
  }

  ctx.restore()
}
