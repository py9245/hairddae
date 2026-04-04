import type { RefObject } from 'react'

type HairCameraStageProps = {
  videoRef: RefObject<HTMLVideoElement | null>
  remoteVideoRef: RefObject<HTMLVideoElement | null>
  frozenFrameCanvasRef: RefObject<HTMLCanvasElement | null>
  hasRemoteVideo: boolean
  showFrozenFrame?: boolean
  localMirrored?: boolean
  remoteMirrored?: boolean
}

export function HairCameraStage({
  videoRef,
  remoteVideoRef,
  frozenFrameCanvasRef,
  hasRemoteVideo,
  showFrozenFrame = false,
  localMirrored = true,
  remoteMirrored = false,
}: HairCameraStageProps) {
  const localMirrorClassName = localMirrored ? '-scale-x-100' : ''
  const remoteMirrorClassName = remoteMirrored ? '-scale-x-100' : ''

  return (
    <>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={
          hasRemoteVideo
            ? `absolute inset-0 h-full w-full object-cover object-center ${localMirrorClassName} opacity-0`
            : `block h-full w-full object-cover object-center ${localMirrorClassName}`
        }
      />

      <video
        ref={remoteVideoRef}
        autoPlay
        playsInline
        muted
        className={
          hasRemoteVideo
            ? `absolute inset-0 z-10 h-full w-full object-cover object-center ${remoteMirrorClassName}`
            : 'hidden'
        }
      />

      <canvas
        ref={frozenFrameCanvasRef}
        className={
          showFrozenFrame
            ? 'pointer-events-none absolute inset-0 z-20 h-full w-full'
            : 'hidden'
        }
      />
    </>
  )
}
