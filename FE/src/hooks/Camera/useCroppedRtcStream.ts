import { useEffect, useMemo, useRef, useState } from 'react'

type UseCroppedRtcStreamArgs = {
  sourceStream: MediaStream | null
  targetAspect?: number
  outputWidth?: number
  fps?: number
}

export function useCroppedRtcStream({
  sourceStream,
  targetAspect = 9 / 20,
  outputWidth = 720,
  fps = 10,
}: UseCroppedRtcStreamArgs) {
  const [croppedStream, setCroppedStream] = useState<MediaStream | null>(null)

  const videoElRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const frameRef = useRef<number | null>(null)

  const outputHeight = useMemo(
    () => Math.round(outputWidth / targetAspect),
    [outputWidth, targetAspect],
  )

  useEffect(() => {
    if (!sourceStream) {
      setCroppedStream(null)
      return
    }

    const video = document.createElement('video')
    video.playsInline = true
    video.muted = true
    video.autoplay = true
    video.srcObject = sourceStream

    const canvas = document.createElement('canvas')
    canvas.width = outputWidth
    canvas.height = outputHeight

    videoElRef.current = video
    canvasRef.current = canvas

    let stopped = false
    let stream: MediaStream | null = null

    function draw() {
      if (stopped || !video.videoWidth || !video.videoHeight) {
        frameRef.current = requestAnimationFrame(draw)
        return
      }

      const ctx = canvas.getContext('2d')
      if (!ctx) {
        frameRef.current = requestAnimationFrame(draw)
        return
      }

      const sourceWidth = video.videoWidth
      const sourceHeight = video.videoHeight
      const sourceAspect = sourceWidth / sourceHeight

      let sx = 0
      let sy = 0
      let sWidth = sourceWidth
      let sHeight = sourceHeight

      if (sourceAspect > targetAspect) {
        sHeight = sourceHeight
        sWidth = sourceHeight * targetAspect
        sx = (sourceWidth - sWidth) / 2
      } else {
        sWidth = sourceWidth
        sHeight = sourceWidth / targetAspect
        sy = (sourceHeight - sHeight) / 2
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(
        video,
        sx,
        sy,
        sWidth,
        sHeight,
        0,
        0,
        canvas.width,
        canvas.height,
      )

      frameRef.current = requestAnimationFrame(draw)
    }

    video
      .play()
      .then(() => {
        draw()
        stream = canvas.captureStream(fps)
        setCroppedStream(stream)
      })
      .catch((error) => {
        console.error('cropped rtc stream start failed:', error)
        setCroppedStream(null)
      })

    return () => {
      stopped = true

      if (frameRef.current != null) {
        cancelAnimationFrame(frameRef.current)
      }

      stream?.getTracks().forEach((track) => {
        track.stop()
      })
      video.pause()
      video.srcObject = null
    }
  }, [fps, outputHeight, outputWidth, sourceStream, targetAspect])

  return croppedStream
}
