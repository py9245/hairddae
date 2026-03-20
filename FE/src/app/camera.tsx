import { useEffect, useMemo, useRef } from 'react'
import FaceLandmarksView from '@/components/Camera/face-landmarks-view'
import { useCroppedRtcStream } from '@/hooks/Camera/useCroppedRtcStream'
import { useUserMedia } from '@/hooks/Camera/useUserMedia'
import {
  RTC_CAPTURE_FPS,
  RTC_CAPTURE_HEIGHT,
  RTC_CAPTURE_WIDTH,
} from '@/lib/Camera/runtime'

export default function Camera() {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const rtcPreviewRef = useRef<HTMLVideoElement | null>(null)

  const mediaConstraints = useMemo<MediaStreamConstraints>(
    () => ({
      video: {
        facingMode: 'user',
        width: { ideal: RTC_CAPTURE_WIDTH, max: RTC_CAPTURE_WIDTH },
        height: { ideal: RTC_CAPTURE_HEIGHT, max: RTC_CAPTURE_HEIGHT },
        frameRate: { ideal: RTC_CAPTURE_FPS, max: RTC_CAPTURE_FPS },
      },
      audio: false,
    }),
    [],
  )

  const cam = useUserMedia({ videoRef, constraints: mediaConstraints })

  const rtcStream = useCroppedRtcStream({
    sourceStream: cam.stream,
    targetAspect: 9 / 20,
    outputWidth: 720,
    fps: RTC_CAPTURE_FPS,
  })

  useEffect(() => {
    const track = rtcStream?.getVideoTracks()[0]
    console.log('rtc cropped track settings:', track?.getSettings())
  }, [rtcStream])

  useEffect(() => {
    const preview = rtcPreviewRef.current
    if (!preview) return

    preview.srcObject = rtcStream ?? null

    return () => {
      if (preview.srcObject === rtcStream) {
        preview.srcObject = null
      }
    }
  }, [rtcStream])

  return (
    <div>
      <FaceLandmarksView
        stream={rtcStream}
        videoRef={videoRef}
        canvasRef={canvasRef}
        overlayCanvasRef={overlayCanvasRef}
      />
    </div>
  )
}
