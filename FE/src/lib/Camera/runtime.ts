const DEFAULT_CAMERA_TARGET_FPS = 24
const MIN_CAMERA_TARGET_FPS = 15
const MAX_CAMERA_TARGET_FPS = 60

function resolveCameraTargetFps(rawValue: string | undefined) {
  const parsed = Number.parseInt(rawValue ?? '', 10)
  if (!Number.isFinite(parsed)) {
    return DEFAULT_CAMERA_TARGET_FPS
  }

  return Math.min(
    MAX_CAMERA_TARGET_FPS,
    Math.max(MIN_CAMERA_TARGET_FPS, parsed),
  )
}

export const CAMERA_TARGET_FPS = resolveCameraTargetFps(
  import.meta.env.VITE_CAMERA_TARGET_FPS,
)

export const CAMERA_FRAME_INTERVAL_MS = 1000 / CAMERA_TARGET_FPS

export const HAIR_TRANSPORT =
  import.meta.env.VITE_HAIR_TRANSPORT === 'ws' ? 'ws' : 'rtc'
