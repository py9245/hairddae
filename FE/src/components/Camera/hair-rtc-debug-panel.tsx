import {
  RTC_CAPTURE_FPS,
  RTC_CAPTURE_HEIGHT,
  RTC_CAPTURE_WIDTH,
  RTC_SENDER_MAX_BITRATE,
} from '@/lib/Camera/runtime'

type HairRtcDebugPanelProps = {
  error?: string | null
  isConnected: boolean
  displayHairId: number
  asset?: {
    poseKey: string
  } | null
  connectionState?: string | null
  metrics: {
    inferenceRttMs: number | null
    processedFps: number | null
  }
  hasRemoteVideo: boolean
  remoteVideoReady: boolean
  isRenderReady: boolean
  remoteVideoSize: {
    width: number
    height: number
  } | null
}

function DebugBadge({
  className = '',
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return (
    <div
      className={`absolute left-2 z-20 rounded bg-black/60 px-2 py-1 text-white ${className}`}
    >
      {children}
    </div>
  )
}

export function HairRtcDebugPanel({
  error,
  isConnected,
  displayHairId,
  asset,
  connectionState,
  metrics,
  hasRemoteVideo,
  remoteVideoReady,
  isRenderReady,
  remoteVideoSize,
}: HairRtcDebugPanelProps) {
  const targetQualityLabel = `${RTC_CAPTURE_WIDTH}x${RTC_CAPTURE_HEIGHT}@${RTC_CAPTURE_FPS} ${(
    RTC_SENDER_MAX_BITRATE / 1_000_000
  ).toFixed(1)}Mbps`

  const currentQualityLabel = remoteVideoSize
    ? `${remoteVideoSize.width}x${remoteVideoSize.height}`
    : '-'

  return (
    <>
      <DebugBadge className="top-2 text-xs">
        {error
          ? error
          : isConnected
            ? 'RTC 연결됨'
            : displayHairId > 0
              ? 'RTC 연결 중'
              : '헤어 선택 전'}
      </DebugBadge>

      <DebugBadge className="top-10 text-[10px]">
        {asset ? `asset ${asset.poseKey}` : '준비 완료'}
      </DebugBadge>

      <DebugBadge className="top-[4.5rem] text-[10px]">
        {`rtc ${connectionState ?? '-'} / rtt ${
          metrics.inferenceRttMs == null
            ? '-'
            : `${Math.round(metrics.inferenceRttMs)}ms`
        }`}
      </DebugBadge>

      <DebugBadge className="top-[6rem] text-[10px]">
        {`proc ${
          metrics.processedFps == null ? '-' : metrics.processedFps.toFixed(1)
        } fps / remote ${
          hasRemoteVideo
            ? 'ready'
            : remoteVideoReady && isRenderReady
              ? 'settling'
              : remoteVideoReady
                ? 'warming'
                : 'waiting'
        }`}
      </DebugBadge>

      <DebugBadge className="top-[7.5rem] text-[10px]">
        {`quality ${currentQualityLabel} / target ${targetQualityLabel}`}
      </DebugBadge>
    </>
  )
}
