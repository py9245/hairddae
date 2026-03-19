import { useEffect, useState } from 'react'

import { getVideoCoverLayout } from '@/lib/Camera/layout'

type UseViewportCaptureStreamArgs = {
  enabled?: boolean
  fps: number
  sourceVideoRef: React.RefObject<HTMLVideoElement | null>
  wrapRef: React.RefObject<HTMLDivElement | null>
}

export function useViewportCaptureStream({
  enabled = true,
  fps,
  sourceVideoRef,
  wrapRef,
}: UseViewportCaptureStreamArgs) {
  const [stream, setStream] = useState<MediaStream | null>(null)

  useEffect(() => {
    if (!enabled) {
      setStream(null)
      return
    }

    const sourceVideo = sourceVideoRef.current
    const wrap = wrapRef.current
    if (!sourceVideo || !wrap) {
      setStream(null)
      return
    }

    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d', {
      alpha: false,
      desynchronized: true,
    })
    if (!context) {
      setStream(null)
      return
    }

    let cancelled = false
    let timerId: number | null = null
    let captureStream: MediaStream | null = null
    const frameIntervalMs = 1000 / Math.max(1, fps)

    const stop = () => {
      if (timerId != null) {
        window.clearTimeout(timerId)
        timerId = null
      }
      captureStream?.getTracks().forEach((track) => {
        track.stop()
      })
      captureStream = null
      setStream(null)
    }

    const draw = () => {
      if (cancelled) {
        return
      }

      const nextSourceVideo = sourceVideoRef.current
      const nextWrap = wrapRef.current
      const width = Math.round(nextWrap?.clientWidth ?? 0)
      const height = Math.round(nextWrap?.clientHeight ?? 0)
      const videoWidth = nextSourceVideo?.videoWidth ?? 0
      const videoHeight = nextSourceVideo?.videoHeight ?? 0

      if (
        nextSourceVideo &&
        width > 0 &&
        height > 0 &&
        videoWidth > 0 &&
        videoHeight > 0
      ) {
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width
          canvas.height = height
        }

        context.clearRect(0, 0, width, height)

        const { offsetX, offsetY, scale } = getVideoCoverLayout(
          width,
          height,
          videoWidth,
          videoHeight,
        )

        context.drawImage(
          nextSourceVideo,
          0,
          0,
          videoWidth,
          videoHeight,
          offsetX,
          offsetY,
          videoWidth * scale,
          videoHeight * scale,
        )

        if (!captureStream) {
          captureStream = canvas.captureStream(fps)
          setStream(captureStream)
        }
      }

      timerId = window.setTimeout(draw, frameIntervalMs)
    }

    draw()

    return () => {
      cancelled = true
      stop()
    }
  }, [enabled, fps, sourceVideoRef, wrapRef])

  return stream
}
