const DEFAULT_CAMERA_SOURCE_WIDTH = 1280
const DEFAULT_CAMERA_SOURCE_HEIGHT = 960
const DEFAULT_CAMERA_SOURCE_FPS = 15
const MIN_CAMERA_FPS = 10
const MAX_CAMERA_FPS = 60

const DEFAULT_RTC_STAGE_WIDTH = 576
const DEFAULT_RTC_STAGE_HEIGHT = 1024
const DEFAULT_RTC_STAGE_FPS = 15
const DEFAULT_RTC_SENDER_START_BITRATE = 1_200_000
const DEFAULT_RTC_SENDER_MAX_BITRATE = 2_500_000
const DEFAULT_RTC_SENDER_MAX_FRAMERATE = 15

function resolveCameraFps(rawValue: string | undefined, fallback: number) {
  const parsed = Number.parseInt(rawValue ?? '', 10)
  if (!Number.isFinite(parsed)) {
    return fallback
  }

  return Math.min(MAX_CAMERA_FPS, Math.max(MIN_CAMERA_FPS, parsed))
}

function resolvePositiveInt(rawValue: string | undefined, fallback: number) {
  const parsed = Number.parseInt(rawValue ?? '', 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback
  }
  return parsed
}

export const CAMERA_SOURCE_WIDTH = resolvePositiveInt(
  import.meta.env.VITE_CAMERA_SOURCE_WIDTH,
  DEFAULT_CAMERA_SOURCE_WIDTH,
)

export const CAMERA_SOURCE_HEIGHT = resolvePositiveInt(
  import.meta.env.VITE_CAMERA_SOURCE_HEIGHT,
  DEFAULT_CAMERA_SOURCE_HEIGHT,
)

export const CAMERA_SOURCE_FPS = resolveCameraFps(
  import.meta.env.VITE_CAMERA_SOURCE_FPS,
  DEFAULT_CAMERA_SOURCE_FPS,
)

export const RTC_STAGE_WIDTH = resolvePositiveInt(
  import.meta.env.VITE_RTC_STAGE_WIDTH,
  DEFAULT_RTC_STAGE_WIDTH,
)

export const RTC_STAGE_HEIGHT = resolvePositiveInt(
  import.meta.env.VITE_RTC_STAGE_HEIGHT,
  DEFAULT_RTC_STAGE_HEIGHT,
)

export const RTC_STAGE_FPS = resolveCameraFps(
  import.meta.env.VITE_RTC_STAGE_FPS,
  DEFAULT_RTC_STAGE_FPS,
)

export const RTC_STAGE_MIRRORED =
  import.meta.env.VITE_RTC_STAGE_MIRRORED !== 'false'

export const RTC_DEBUG_LOGS = import.meta.env.VITE_RTC_DEBUG_LOGS === 'true'

export const RTC_SENDER_START_BITRATE = resolvePositiveInt(
  import.meta.env.VITE_RTC_SENDER_START_BITRATE,
  DEFAULT_RTC_SENDER_START_BITRATE,
)

export const RTC_SENDER_MAX_BITRATE = resolvePositiveInt(
  import.meta.env.VITE_RTC_SENDER_MAX_BITRATE,
  DEFAULT_RTC_SENDER_MAX_BITRATE,
)

export const RTC_SENDER_MAX_FRAMERATE = resolveCameraFps(
  import.meta.env.VITE_RTC_SENDER_MAX_FRAMERATE ??
    String(DEFAULT_RTC_SENDER_MAX_FRAMERATE),
  DEFAULT_RTC_SENDER_MAX_FRAMERATE,
)

export const HAIR_TRANSPORT = 'rtc'
