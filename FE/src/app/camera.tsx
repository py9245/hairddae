import { useMemo, useRef } from 'react'
import FaceLandmarksView from '@/components/Camera/face-landmarks-view'
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

  return (
    <FaceLandmarksView
      stream={cam.stream}
      videoRef={videoRef}
      canvasRef={canvasRef}
      overlayCanvasRef={overlayCanvasRef}
    />
  )
}