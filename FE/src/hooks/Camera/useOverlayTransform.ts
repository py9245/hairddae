// hooks/hair/useOverlayTransform.ts
import { useMemo } from 'react'

export type NLM = { x: number; y: number; z?: number }

function fitContainRect(vw: number, vh: number, W: number, H: number) {
  const s = Math.min(W / vw, H / vh)
  const rw = vw * s
  const rh = vh * s
  const ox = (W - rw) / 2
  const oy = (H - rh) / 2
  return { s, ox, oy }
}

export function useOverlayTransform({
  wrapRef,
  videoRef,
  landmarks,
  baseEyePx = 260,
  pngAnchor = { x: 250, y: 280 }, // ✅ PNG에서 '이마'가 찍혀야 하는 점
  offsetPx = { x: 0, y: 0 },
}: {
  wrapRef: React.RefObject<HTMLElement | null>
  videoRef: React.RefObject<HTMLVideoElement | null>
  landmarks: NLM[] | null
  baseEyePx?: number
  pngAnchor?: { x: number; y: number }
  offsetPx?: { x: number; y: number } // ✅ 추가
}) {
  return useMemo(() => {
    const wrap = wrapRef.current
    const v = videoRef.current
    if (!wrap || !v) return null
    if (!landmarks || landmarks.length < 264) return null

    const vw = v.videoWidth
    const vh = v.videoHeight
    if (!vw || !vh) return null

    const rect = wrap.getBoundingClientRect()
    const W = rect.width
    const H = rect.height
    if (!W || !H) return null

    const { s, ox, oy } = fitContainRect(vw, vh, W, H)

    const F = landmarks[10]
    const L = landmarks[33]
    const R = landmarks[263]
    if (!F || !L || !R) return null

    const Fp = { x: ox + F.x * vw * s, y: oy + F.y * vh * s }
    const Lp = { x: ox + L.x * vw * s, y: oy + L.y * vh * s }
    const Rp = { x: ox + R.x * vw * s, y: oy + R.y * vh * s }

    const dx = Rp.x - Lp.x
    const dy = Rp.y - Lp.y
    const eyeDist = Math.hypot(dx, dy)
    if (!eyeDist) return null

    const scale = eyeDist / baseEyePx

    const rot = Math.atan2(dy, dx)

    const ax = pngAnchor.x
    const ay = pngAnchor.y

    const tx0 = Fp.x + offsetPx.x
    const ty0 = Fp.y + offsetPx.y

    return `translate(${tx0}px, ${ty0}px) rotate(${rot}rad) scale(${scale}) translate(${-ax}px, ${-ay}px)`
  }, [
    wrapRef,
    videoRef,
    landmarks,
    baseEyePx,
    pngAnchor.x,
    pngAnchor.y,
    offsetPx.x,
    offsetPx.y,
  ])
}
