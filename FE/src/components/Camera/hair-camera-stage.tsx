import type { RefObject } from 'react'

type HairCameraStageProps = {
  videoRef: RefObject<HTMLVideoElement | null>
  remoteVideoRef: RefObject<HTMLVideoElement | null>
  canvasRef: RefObject<HTMLCanvasElement | null>
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>
  hasRemoteVideo: boolean
}

export function HairCameraStage({
  videoRef,
  remoteVideoRef,
  canvasRef,
  overlayCanvasRef,
  hasRemoteVideo,
}: HairCameraStageProps) {
  return (
    <>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={
          hasRemoteVideo
            ? 'absolute inset-0 h-full w-full object-cover -scale-x-100 opacity-0'
            : 'block h-full w-full object-cover -scale-x-100'
        }
      />

      <video
        ref={remoteVideoRef}
        autoPlay
        playsInline
        muted
        className={
          hasRemoteVideo
            ? 'absolute inset-0 z-10 h-full w-full object-cover -scale-x-100'
            : 'hidden'
        }
      />

      <canvas
        ref={canvasRef}
        className="pointer-events-none absolute inset-0 hidden h-full w-full -scale-x-100"
      />

      <canvas ref={overlayCanvasRef} className="hidden" />
    </>
  )
}
