import { useEffect, useMemo, useRef, useState } from 'react'
import FaceLandmarksView from '@/components/Camera/face-landmarks-view'
import { useCroppedRtcStream } from '@/hooks/Camera/useCroppedRtcStream'
import { useUserMedia } from '@/hooks/Camera/useUserMedia'
import {
  DEFAULT_RTC_VIDEO_SETTINGS,
  type RtcVideoSettings,
} from '@/lib/Camera/rtc-settings'

export default function Camera() {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const rtcPreviewRef = useRef<HTMLVideoElement | null>(null)
  const [videoSettings, setVideoSettings] = useState<RtcVideoSettings>(
    DEFAULT_RTC_VIDEO_SETTINGS,
  )

  const mediaConstraints = useMemo<MediaStreamConstraints>(
    () => ({
      video: {
        facingMode: 'user',
        width: {
          ideal: videoSettings.captureWidth,
          max: videoSettings.captureWidth,
        },
        height: {
          ideal: videoSettings.captureHeight,
          max: videoSettings.captureHeight,
        },
        frameRate: { ideal: videoSettings.fps, max: videoSettings.fps },
      },
      audio: false,
    }),
    [videoSettings],
  )

  const cam = useUserMedia({ videoRef, constraints: mediaConstraints })

  const rtcStream = useCroppedRtcStream({
    sourceStream: cam.stream,
    targetAspect: 9 / 20,
    outputWidth: videoSettings.outputWidth,
    fps: videoSettings.fps,
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
        videoSettings={videoSettings}
        onVideoSettingsChange={setVideoSettings}
      />
    </div>
  )
}
