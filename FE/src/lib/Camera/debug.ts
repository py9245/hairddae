import { RTC_DEBUG_LOGS } from '@/lib/Camera/runtime'

const RTC_DEBUG_STORAGE_KEY = 'rtc-debug-logs'

export function isRtcDebugEnabled() {
  if (RTC_DEBUG_LOGS) {
    return true
  }

  if (typeof window === 'undefined') {
    return false
  }

  try {
    return window.localStorage.getItem(RTC_DEBUG_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

export function logRtcDebug(label: string, payload?: unknown) {
  if (!isRtcDebugEnabled()) {
    return
  }

  if (payload === undefined) {
    console.info(`[RTC_DEBUG] ${label}`)
    return
  }

  console.info(`[RTC_DEBUG] ${label}`, payload)
}

export function describeMediaTrack(track: MediaStreamTrack | null | undefined) {
  if (!track) {
    return null
  }

  return {
    id: track.id,
    kind: track.kind,
    label: track.label,
    enabled: track.enabled,
    muted: track.muted,
    readyState: track.readyState,
  }
}

export function describeMediaStream(stream: MediaStream | null | undefined) {
  if (!stream) {
    return null
  }

  return {
    id: stream.id,
    active: stream.active,
    tracks: stream.getTracks().map((track) => describeMediaTrack(track)),
  }
}
