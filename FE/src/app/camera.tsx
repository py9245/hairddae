import { useSearch } from '@tanstack/react-router'
import { useMemo, useRef } from 'react'

import { HairCameraView } from '@/components/Camera/hair-camera-view'
import { useUserMedia } from '@/hooks/Camera/useUserMedia'
import {
  CAMERA_SOURCE_FPS,
  CAMERA_SOURCE_HEIGHT,
  CAMERA_SOURCE_WIDTH,
} from '@/lib/Camera/runtime'

export default function Camera() {
  const { applyLatest, hairId } = useSearch({ from: '/camera' })
  const videoRef = useRef<HTMLVideoElement | null>(null)

  const mediaConstraints = useMemo<MediaStreamConstraints>(
    () => ({
      video: {
        facingMode: 'user',
        width: { ideal: CAMERA_SOURCE_WIDTH, max: CAMERA_SOURCE_WIDTH },
        height: { ideal: CAMERA_SOURCE_HEIGHT, max: CAMERA_SOURCE_HEIGHT },
        frameRate: { ideal: CAMERA_SOURCE_FPS, max: CAMERA_SOURCE_FPS },
      },
      audio: false,
    }),
    [],
  )

  const cam = useUserMedia({ videoRef, constraints: mediaConstraints })

  return (
    <HairCameraView
      videoRef={videoRef}
      cameraStream={cam.stream}
      cameraReady={cam.ready}
      cameraError={cam.error}
      initialHairId={hairId ?? null}
      autoSelectFirstHair={applyLatest ?? false}
    />
  )
}
