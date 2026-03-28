import { useEffect, useState } from 'react'

import { describeMediaStream, logRtcDebug } from '@/lib/Camera/debug'
import { getVideoCoverLayout } from '@/lib/Camera/layout'

type VideoElementWithFrameCallback = HTMLVideoElement & {
  requestVideoFrameCallback?: (
    callback: (now: number, metadata: unknown) => void,
  ) => number
  cancelVideoFrameCallback?: (handle: number) => void
}

type UseViewportCaptureStreamArgs = {
  enabled?: boolean
  fps: number
  width: number
  height: number
  mirror?: boolean
  sourceVideoRef: React.RefObject<HTMLVideoElement | null>
}

export function useViewportCaptureStream({
  enabled = true,
  fps,
  width,
  height,
  mirror = true,
  sourceVideoRef,
}: UseViewportCaptureStreamArgs) {
  const [stream, setStream] = useState<MediaStream | null>(null)

  useEffect(() => {
    if (!enabled) {
      logRtcDebug('viewport capture disabled')
      setStream(null)
      return
    }

    const sourceVideo = sourceVideoRef.current
    if (!sourceVideo) {
      logRtcDebug('viewport capture source missing')
      setStream(null)
      return
    }

    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d', {
      alpha: false,
      desynchronized: true,
    })
    if (!context) {
      logRtcDebug('viewport capture context unavailable')
      setStream(null)
      return
    }

    let cancelled = false
    let timerId: number | null = null
    let frameCallbackId: number | null = null
    let captureStream: MediaStream | null = null
    let lastDrawAt = -Infinity
    const frameIntervalMs = 1000 / Math.max(1, fps)
    const videoWithFrameCallback = sourceVideo as VideoElementWithFrameCallback

    const stop = () => {
      logRtcDebug('viewport capture stop', {
        stream: describeMediaStream(captureStream),
      })
      if (timerId != null) {
        window.clearTimeout(timerId)
        timerId = null
      }
      if (
        frameCallbackId != null &&
        typeof videoWithFrameCallback.cancelVideoFrameCallback === 'function'
      ) {
        videoWithFrameCallback.cancelVideoFrameCallback(frameCallbackId)
        frameCallbackId = null
      }
      captureStream?.getTracks().forEach((track) => {
        track.stop()
      })
      captureStream = null
      setStream(null)
    }

    const drawFrame = (now: number) => {
      const nextSourceVideo = sourceVideoRef.current
      const videoWidth = nextSourceVideo?.videoWidth ?? 0
      const videoHeight = nextSourceVideo?.videoHeight ?? 0

      if (
        nextSourceVideo &&
        width > 0 &&
        height > 0 &&
        videoWidth > 0 &&
        videoHeight > 0 &&
        now - lastDrawAt >= frameIntervalMs - 1
      ) {
        lastDrawAt = now

        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width
          canvas.height = height
        }

        const { offsetX, offsetY, scale } = getVideoCoverLayout(
          width,
          height,
          videoWidth,
          videoHeight,
        )

        context.clearRect(0, 0, width, height)
        context.imageSmoothingEnabled = true
        context.imageSmoothingQuality = 'medium'
        if (mirror) {
          context.save()
          context.translate(width, 0)
          context.scale(-1, 1)
        }
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
        if (mirror) {
          context.restore()
        }

        if (!captureStream) {
          captureStream = canvas.captureStream(fps)
          logRtcDebug('viewport capture stream created', {
            width,
            height,
            fps,
            sourceVideoWidth: videoWidth,
            sourceVideoHeight: videoHeight,
            stream: describeMediaStream(captureStream),
          })
          setStream(captureStream)
        }
      }
    }

    const scheduleTimeoutDraw = () => {
      if (cancelled) {
        return
      }
      timerId = window.setTimeout(() => {
        drawFrame(performance.now())
        scheduleTimeoutDraw()
      }, frameIntervalMs)
    }

    const scheduleVideoFrameDraw = () => {
      if (
        cancelled ||
        typeof videoWithFrameCallback.requestVideoFrameCallback !== 'function'
      ) {
        return
      }
      frameCallbackId = videoWithFrameCallback.requestVideoFrameCallback(
        (now) => {
          drawFrame(now)
          scheduleVideoFrameDraw()
        },
      )
    }

    if (
      typeof videoWithFrameCallback.requestVideoFrameCallback === 'function'
    ) {
      scheduleVideoFrameDraw()
    } else {
      scheduleTimeoutDraw()
    }

    return () => {
      cancelled = true
      stop()
    }
  }, [enabled, fps, height, mirror, sourceVideoRef, width])

  return stream
}
