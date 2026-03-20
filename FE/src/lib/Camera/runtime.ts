const DEFAULT_CAMERA_TARGET_FPS = 24
const MIN_CAMERA_TARGET_FPS = 15
const MAX_CAMERA_TARGET_FPS = 60
const DEFAULT_RTC_CAPTURE_WIDTH = 1920
const DEFAULT_RTC_CAPTURE_HEIGHT = 1080
const DEFAULT_RTC_CAPTURE_FPS = 10
const DEFAULT_RTC_SENDER_MAX_BITRATE = 8_000_000
const DEFAULT_RTC_SENDER_MAX_FRAMERATE = 10

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

function resolvePositiveInt(rawValue: string | undefined, fallback: number) {
  const parsed = Number.parseInt(rawValue ?? '', 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback
  }
  return parsed
}

export const CAMERA_TARGET_FPS = resolveCameraTargetFps(
  import.meta.env.VITE_CAMERA_TARGET_FPS,
)

export const CAMERA_FRAME_INTERVAL_MS = 1000 / CAMERA_TARGET_FPS

export const RTC_CAPTURE_WIDTH = resolvePositiveInt(
  import.meta.env.VITE_RTC_CAPTURE_WIDTH,
  DEFAULT_RTC_CAPTURE_WIDTH,
)

export const RTC_CAPTURE_HEIGHT = resolvePositiveInt(
  import.meta.env.VITE_RTC_CAPTURE_HEIGHT,
  DEFAULT_RTC_CAPTURE_HEIGHT,
)

export const RTC_CAPTURE_FPS = resolveCameraTargetFps(
  import.meta.env.VITE_RTC_CAPTURE_FPS ?? String(DEFAULT_RTC_CAPTURE_FPS),
)

export const RTC_SENDER_MAX_BITRATE = resolvePositiveInt(
  import.meta.env.VITE_RTC_SENDER_MAX_BITRATE,
  DEFAULT_RTC_SENDER_MAX_BITRATE,
)

export const RTC_SENDER_MAX_FRAMERATE = resolveCameraTargetFps(
  import.meta.env.VITE_RTC_SENDER_MAX_FRAMERATE ??
    String(DEFAULT_RTC_SENDER_MAX_FRAMERATE),
)

export const HAIR_TRANSPORT = 'rtc'
