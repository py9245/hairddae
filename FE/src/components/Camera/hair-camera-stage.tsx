import type { RefObject } from 'react'

type HairCameraStageProps = {
  videoRef: RefObject<HTMLVideoElement | null>
  remoteVideoRef: RefObject<HTMLVideoElement | null>
  hasRemoteVideo: boolean
  localMirrored?: boolean
  remoteMirrored?: boolean
}

export function HairCameraStage({
  videoRef,
  remoteVideoRef,
  hasRemoteVideo,
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
            ? `absolute inset-0 h-full w-full object-cover ${localMirrorClassName} opacity-0`
            : `block h-full w-full object-cover ${localMirrorClassName}`
        }
      />

      <video
        ref={remoteVideoRef}
        autoPlay
        playsInline
        muted
        className={
          hasRemoteVideo
            ? `absolute inset-0 z-10 h-full w-full object-cover ${remoteMirrorClassName}`
            : 'hidden'
        }
      />
    </>
  )
}
