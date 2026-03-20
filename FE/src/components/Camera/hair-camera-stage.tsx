import type { RefObject } from 'react'

type HairCameraStageProps = {
  videoRef: RefObject<HTMLVideoElement | null>
  remoteVideoRef: RefObject<HTMLVideoElement | null>
  canvasRef: RefObject<HTMLCanvasElement | null>
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>
  hasRemoteVideo: boolean
  mirrored?: boolean
}

export function HairCameraStage({
  videoRef,
  remoteVideoRef,
  canvasRef,
  overlayCanvasRef,
  hasRemoteVideo,
  mirrored = true,
}: HairCameraStageProps) {
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div
        className="absolute inset-0"
        style={{
          transform: mirrored ? 'scaleX(-1)' : 'scaleX(1)',
          transformOrigin: 'center',
        }}
      >
        {hasRemoteVideo ? (
          <video
            ref={remoteVideoRef}
            autoPlay
            playsInline
            muted
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="absolute inset-0 h-full w-full object-cover"
          />
        )}

        <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
        <canvas
          ref={overlayCanvasRef}
          className="absolute inset-0 h-full w-full"
        />
      </div>
    </div>
  )
}
