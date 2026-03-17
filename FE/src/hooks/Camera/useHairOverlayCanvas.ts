import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useEffect, useRef, useState } from 'react'

import { syncCanvasSize } from '@/lib/Camera/drawLandmarks'
import type { InferenceAssetBundle } from '@/lib/Camera/inference'
import {
  drawOverlayFrame,
  getCachedOverlayAssetBundle,
  loadOverlayAssetBundle,
} from '@/lib/Camera/overlay'

type UseHairOverlayCanvasArgs = {
  canvasRef: React.RefObject<HTMLCanvasElement | null>
  videoRef: React.RefObject<HTMLVideoElement | null>
  landmarks: NormalizedLandmark[] | null
  asset: InferenceAssetBundle | null
}

type LoadedBundle = Awaited<ReturnType<typeof loadOverlayAssetBundle>>

type DisplayedOverlay = {
  asset: InferenceAssetBundle
  bundle: LoadedBundle
}

type OverlayMetrics = {
  drawFps: number | null
  bundleReady: boolean
  bundleLoadMs: number | null
  displayedAssetId: string | null
}

export function useHairOverlayCanvas({
  canvasRef,
  videoRef,
  landmarks,
  asset,
}: UseHairOverlayCanvasArgs) {
  const activeAssetIdRef = useRef<string | null>(null)
  const lastDrawAtRef = useRef<number | null>(null)
  const drawFpsEmaRef = useRef<number | null>(null)
  const [bundleVersion, setBundleVersion] = useState(0)
  const [displayedOverlay, setDisplayedOverlay] = useState<DisplayedOverlay | null>(null)
  const [metrics, setMetrics] = useState<OverlayMetrics>({
    drawFps: null,
    bundleReady: false,
    bundleLoadMs: null,
    displayedAssetId: null,
  })

  useEffect(() => {
    const assetId = asset?.assetId ?? null
    activeAssetIdRef.current = assetId

    if (!asset || !assetId) {
      setDisplayedOverlay(null)
      lastDrawAtRef.current = null
      drawFpsEmaRef.current = null
      setMetrics({
        drawFps: null,
        bundleReady: false,
        bundleLoadMs: null,
        displayedAssetId: null,
      })
      return
    }

    const cached = getCachedOverlayAssetBundle(assetId)
    if (cached) {
      setMetrics((current) => ({
        ...current,
        bundleReady: true,
        bundleLoadMs: 0,
        displayedAssetId: assetId,
      }))
      return
    }

    let cancelled = false
    const loadStartedAt = performance.now()
    setMetrics((current) => ({
      ...current,
      bundleReady: false,
      displayedAssetId: assetId,
    }))

    loadOverlayAssetBundle(asset)
      .then((bundle) => {
        if (cancelled || !bundle) return
        setBundleVersion((current) => current + 1)
        if (activeAssetIdRef.current === assetId) {
          setMetrics((current) => ({
            ...current,
            bundleReady: true,
            bundleLoadMs: performance.now() - loadStartedAt,
            displayedAssetId: assetId,
          }))
        }
      })
      .catch((caught) => {
        console.error('overlay asset load failed:', caught)
      })

    return () => {
      cancelled = true
    }
  }, [asset?.assetId, asset?.hairRgbaUrl, asset?.anchorsUrl])

  useEffect(() => {
    const assetId = asset?.assetId ?? null
    if (!asset || !assetId) {
      setDisplayedOverlay(null)
      return
    }

    const cached = getCachedOverlayAssetBundle(assetId)
    if (!cached) {
      return
    }

    setDisplayedOverlay({
      asset,
      bundle: cached,
    })
  }, [asset, bundleVersion])

  useEffect(() => {
    const canvas = canvasRef.current
    const video = videoRef.current
    if (!canvas) return

    syncCanvasSize(canvas)
    drawOverlayFrame({
      canvas,
      videoWidth: video?.videoWidth ?? 0,
      videoHeight: video?.videoHeight ?? 0,
      landmarks: landmarks ?? [],
      bundle: displayedOverlay?.bundle ?? null,
      renderTask: displayedOverlay?.asset.renderTask ?? null,
    })

    if (!displayedOverlay?.bundle || (landmarks?.length ?? 0) === 0) {
      return
    }

    const now = performance.now()
    if (lastDrawAtRef.current != null) {
      const deltaMs = now - lastDrawAtRef.current
      if (deltaMs > 0) {
        const nextFps = 1000 / deltaMs
        drawFpsEmaRef.current =
          drawFpsEmaRef.current == null
            ? nextFps
            : drawFpsEmaRef.current * 0.8 + nextFps * 0.2
        setMetrics((current) => ({
          ...current,
          drawFps: drawFpsEmaRef.current,
        }))
      }
    }
    lastDrawAtRef.current = now
  }, [canvasRef, displayedOverlay, landmarks, videoRef])

  return metrics
}
