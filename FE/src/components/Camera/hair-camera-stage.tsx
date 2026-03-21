import type { RefObject } from 'react'

type HairCameraStageProps = {
  videoRef: RefObject<HTMLVideoElement | null>
  remoteVideoRef: RefObject<HTMLVideoElement | null>
  hasRemoteVideo: boolean
  mirrored?: boolean
}

export function HairCameraStage({
  videoRef,
  remoteVideoRef,
  hasRemoteVideo,
  mirrored = true,
}: HairCameraStageProps) {
  const mirrorClassName = mirrored ? '-scale-x-100' : ''

  return (
    <>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={
          hasRemoteVideo
            ? `absolute inset-0 h-full w-full object-cover ${mirrorClassName} opacity-0`
            : `block h-full w-full object-cover ${mirrorClassName}`
        }
      />

      <video
        ref={remoteVideoRef}
        autoPlay
        playsInline
        muted
        className={
          hasRemoteVideo
            ? `absolute inset-0 z-10 h-full w-full object-cover ${mirrorClassName}`
            : 'hidden'
        }
      />
    </>
  )
}
