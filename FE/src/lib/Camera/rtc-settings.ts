export type RtcCaptureResolution = {
  id: string
  label: string
  width: number
  height: number
}

export type RtcVideoSettings = {
  captureWidth: number
  captureHeight: number
  fps: number
  outputWidth: number
  senderMaxBitrate: number
  senderMaxFramerate: number
}

export const RTC_CAPTURE_RESOLUTION_OPTIONS: RtcCaptureResolution[] = [
  { id: 'low', label: '360x800', width: 360, height: 800 },
  { id: 'medium', label: '540x1200', width: 540, height: 1200 },
  { id: 'high', label: '720x1600', width: 720, height: 1600 },
]

export const RTC_FPS_OPTIONS = [15] as const

const DEFAULT_RESOLUTION = RTC_CAPTURE_RESOLUTION_OPTIONS[0]
const DEFAULT_FPS = 15
const DEFAULT_OUTPUT_WIDTH = 360
const DEFAULT_SENDER_MAX_BITRATE = 8_000_000

export const DEFAULT_RTC_VIDEO_SETTINGS: RtcVideoSettings = {
  captureWidth: DEFAULT_RESOLUTION.width,
  captureHeight: DEFAULT_RESOLUTION.height,
  fps: DEFAULT_FPS,
  outputWidth: DEFAULT_OUTPUT_WIDTH,
  senderMaxBitrate: DEFAULT_SENDER_MAX_BITRATE,
  senderMaxFramerate: DEFAULT_FPS,
}

export function buildRtcVideoSettings(
  resolution: RtcCaptureResolution,
  fps: number,
): RtcVideoSettings {
  return {
    captureWidth: resolution.width,
    captureHeight: resolution.height,
    fps,
    outputWidth: resolution.width,
    senderMaxBitrate: DEFAULT_SENDER_MAX_BITRATE,
    senderMaxFramerate: fps,
  }
}

export function findRtcResolutionOption(width: number, height: number) {
  return (
    RTC_CAPTURE_RESOLUTION_OPTIONS.find(
      (option) => option.width === width && option.height === height,
    ) ?? DEFAULT_RESOLUTION
  )
}
