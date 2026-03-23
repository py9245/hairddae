import { useCallback, useEffect, useRef, useState } from 'react'

import {
  getOrCreateDeviceId,
  type HairApplyV2Response,
  type InferenceAssetBundle,
  parseInferenceMessage,
  postHairApplyResumeV2,
  postHairApplyStartV2,
  postRtcOffer,
} from '@/lib/Camera/inference'
import {
  RTC_SENDER_MAX_BITRATE,
  RTC_SENDER_MAX_FRAMERATE,
} from '@/lib/Camera/runtime'

type UseHairRtcSessionArgs = {
  enabled?: boolean
  hairId?: number | null
  stream: MediaStream | null
}

type HairRtcMetrics = {
  inferenceRttMs: number | null
  processedFps: number | null
  queueDepth: number
  droppedPendingCount: number
  transportRoundTripTimeMs: number | null
  estimatedOneWayTransportMs: number | null
  availableOutgoingBitrateKbps: number | null
  outboundBitrateKbps: number | null
  inboundBitrateKbps: number | null
  outboundFramesPerSecond: number | null
  inboundFramesPerSecond: number | null
  outboundFrameWidth: number | null
  outboundFrameHeight: number | null
  inboundFrameWidth: number | null
  inboundFrameHeight: number | null
  serverProcessingMs: number | null
}

type HairRtcDebugLog = {
  atIso: string
  type: 'connected' | 'processed' | 'heartbeat_ack' | 'error'
  summary: string
  raw: string
}

type HairRtcTransportSnapshot = Pick<
  HairRtcMetrics,
  | 'transportRoundTripTimeMs'
  | 'estimatedOneWayTransportMs'
  | 'availableOutgoingBitrateKbps'
  | 'outboundBitrateKbps'
  | 'inboundBitrateKbps'
  | 'outboundFramesPerSecond'
  | 'inboundFramesPerSecond'
  | 'outboundFrameWidth'
  | 'outboundFrameHeight'
  | 'inboundFrameWidth'
  | 'inboundFrameHeight'
>

const RECONNECT_DELAY_MS = 800
const ICE_GATHERING_TIMEOUT_MS = 1500
const REMOTE_READY_MIN_PROCESSED = 1
const REMOTE_READY_MIN_STABLE_ASSET = 1
const RTC_STATS_POLL_INTERVAL_MS = 1000
const MAX_DEBUG_LOGS = 8

function createEmptyTransportSnapshot(): HairRtcTransportSnapshot {
  return {
    transportRoundTripTimeMs: null,
    estimatedOneWayTransportMs: null,
    availableOutgoingBitrateKbps: null,
    outboundBitrateKbps: null,
    inboundBitrateKbps: null,
    outboundFramesPerSecond: null,
    inboundFramesPerSecond: null,
    outboundFrameWidth: null,
    outboundFrameHeight: null,
    inboundFrameWidth: null,
    inboundFrameHeight: null,
  }
}

function readStatNumber(report: RTCStats, key: string) {
  const value = (report as RTCStats & Record<string, unknown>)[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function readStatBoolean(report: RTCStats, key: string) {
  const value = (report as RTCStats & Record<string, unknown>)[key]
  return typeof value === 'boolean' ? value : null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value != null && !Array.isArray(value)
}

function readNestedNumber(
  source: unknown,
  path: readonly string[],
): number | null {
  let current: unknown = source
  for (const part of path) {
    if (!isRecord(current) || !(part in current)) {
      return null
    }
    current = current[part]
  }

  return typeof current === 'number' && Number.isFinite(current) ? current : null
}

function extractServerProcessingMs(rawMessage: unknown) {
  const candidatePaths = [
    ['processing_ms'],
    ['server_processing_ms'],
    ['inference_ms'],
    ['elapsed_ms'],
    ['total_processing_ms'],
    ['timings', 'processing_ms'],
    ['timings', 'inference_ms'],
    ['timings', 'total_ms'],
    ['metrics', 'processing_ms'],
    ['metrics', 'inference_ms'],
    ['metrics', 'total_ms'],
    ['debug', 'processing_ms'],
    ['debug', 'inference_ms'],
    ['profiling', 'processing_ms'],
    ['profiling', 'inference_ms'],
    ['profiling', 'total_ms'],
    ['log', 'processing_ms'],
    ['log', 'inference_ms'],
  ] as const

  for (const path of candidatePaths) {
    const value = readNestedNumber(rawMessage, path)
    if (value != null) {
      return value
    }
  }

  return null
}

function stringifyDebugPayload(rawMessage: unknown) {
  try {
    return JSON.stringify(rawMessage)
  } catch {
    return String(rawMessage)
  }
}

async function configureRtcSender(sender: RTCRtpSender) {
  const track = sender.track
  if (!track || track.kind !== 'video') {
    return
  }

  try {
    track.contentHint = 'motion'
  } catch {}

  const parameters = sender.getParameters()
  const encodings =
    parameters.encodings && parameters.encodings.length > 0
      ? parameters.encodings.map((encoding) => ({ ...encoding }))
      : [{}]

  encodings[0] = {
    ...encodings[0],
    maxBitrate: RTC_SENDER_MAX_BITRATE,
    maxFramerate: RTC_SENDER_MAX_FRAMERATE,
    scaleResolutionDownBy: 1,
  }

  try {
    await sender.setParameters({
      ...parameters,
      encodings,
    })
  } catch (error) {
    console.warn('RTC sender parameter update failed:', error)
  }
}

function waitForIceGatheringComplete(peerConnection: RTCPeerConnection) {
  if (peerConnection.iceGatheringState === 'complete') {
    return Promise.resolve()
  }

  return new Promise<void>((resolve) => {
    let resolved = false
    const timeoutId = window.setTimeout(() => {
      if (resolved) {
        return
      }
      resolved = true
      console.warn('RTC ICE gathering timed out before completion')
      peerConnection.removeEventListener(
        'icegatheringstatechange',
        handleStateChange,
      )
      resolve()
    }, ICE_GATHERING_TIMEOUT_MS)

    const handleStateChange = () => {
      if (resolved || peerConnection.iceGatheringState !== 'complete') {
        return
      }
      resolved = true
      window.clearTimeout(timeoutId)
      peerConnection.removeEventListener(
        'icegatheringstatechange',
        handleStateChange,
      )
      resolve()
    }

    peerConnection.addEventListener(
      'icegatheringstatechange',
      handleStateChange,
    )
  })
}

export function useHairRtcSession({
  enabled = true,
  hairId,
  stream,
}: UseHairRtcSessionArgs) {
  const deviceIdRef = useRef<string>(getOrCreateDeviceId())
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null)
  const dataChannelRef = useRef<RTCDataChannel | null>(null)
  const sessionRef = useRef<HairApplyV2Response | null>(null)
  const sessionHairIdRef = useRef<number | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const statsTimerRef = useRef<number | null>(null)
  const lastProcessedAtRef = useRef<number | null>(null)
  const processedCountRef = useRef(0)
  const stableAssetCountRef = useRef(0)
  const lastAssetIdRef = useRef<string | null>(null)
  const processedFpsEmaRef = useRef<number | null>(null)
  const transportSnapshotRef = useRef<HairRtcTransportSnapshot>(
    createEmptyTransportSnapshot(),
  )
  const lastServerProcessingMsRef = useRef<number | null>(null)
  const lastStatsSampleRef = useRef<{
    timestampMs: number | null
    outboundBytes: number | null
    inboundBytes: number | null
  }>({
    timestampMs: null,
    outboundBytes: null,
    inboundBytes: null,
  })
  const bootstrapRequestRef = useRef(0)
  const latestEnabledRef = useRef(enabled)
  const latestHairIdRef = useRef<number | null>(hairId ?? null)
  const latestStreamRef = useRef<MediaStream | null>(stream)
  const remoteStreamRef = useRef<MediaStream | null>(null)
  const reconnectingRef = useRef(false)
  const manualCloseRef = useRef(false)
  const isRenderReadyRef = useRef(false)

  const [connectionState, setConnectionState] =
    useState<RTCPeerConnectionState>('new')
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null)
  const [asset, setAsset] = useState<InferenceAssetBundle | null>(null)
  const [isRenderReady, setIsRenderReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reconnectVersion, setReconnectVersion] = useState(0)
  const [metrics, setMetrics] = useState<HairRtcMetrics>({
    inferenceRttMs: null,
    processedFps: null,
    queueDepth: 0,
    droppedPendingCount: 0,
    ...createEmptyTransportSnapshot(),
    serverProcessingMs: null,
  })
  const [debugLogs, setDebugLogs] = useState<HairRtcDebugLog[]>([])

  latestEnabledRef.current = enabled
  latestHairIdRef.current = hairId ?? null
  latestStreamRef.current = stream
  isRenderReadyRef.current = isRenderReady

  const clearReconnect = useCallback(() => {
    if (reconnectTimerRef.current == null) {
      return
    }
    window.clearTimeout(reconnectTimerRef.current)
    reconnectTimerRef.current = null
  }, [])
  const clearStatsPolling = useCallback(() => {
    if (statsTimerRef.current != null) {
      window.clearInterval(statsTimerRef.current)
      statsTimerRef.current = null
    }

    lastStatsSampleRef.current = {
      timestampMs: null,
      outboundBytes: null,
      inboundBytes: null,
    }
    transportSnapshotRef.current = createEmptyTransportSnapshot()
  }, [])

  const appendDebugLog = useCallback((entry: HairRtcDebugLog) => {
    console.info('[hair-rtc]', entry.summary, entry.raw)
    setDebugLogs((previous) => [entry, ...previous].slice(0, MAX_DEBUG_LOGS))
  }, [])

  const teardownConnection = useCallback((manual: boolean) => {
    manualCloseRef.current = manual

    dataChannelRef.current?.close()
    dataChannelRef.current = null

    peerConnectionRef.current?.close()
    peerConnectionRef.current = null

    remoteStreamRef.current?.getTracks().forEach((track) => {
      track.stop()
    })
    remoteStreamRef.current = null
    setRemoteStream(null)
    setConnectionState('closed')
  }, [])

  const resetMetrics = useCallback(() => {
    lastProcessedAtRef.current = null
    processedCountRef.current = 0
    stableAssetCountRef.current = 0
    lastAssetIdRef.current = null
    processedFpsEmaRef.current = null
    isRenderReadyRef.current = false
    lastServerProcessingMsRef.current = null
    transportSnapshotRef.current = createEmptyTransportSnapshot()
    setIsRenderReady(false)
    setMetrics({
      inferenceRttMs: null,
      processedFps: null,
      queueDepth: 0,
      droppedPendingCount: 0,
      ...createEmptyTransportSnapshot(),
      serverProcessingMs: null,
    })
    setDebugLogs([])
  }, [])

  const resetRuntime = useCallback(
    ({ clearSession }: { clearSession: boolean }) => {
      clearReconnect()
      clearStatsPolling()
      reconnectingRef.current = false
      teardownConnection(true)
      resetMetrics()
      setAsset(null)
      setError(null)
      if (clearSession) {
        sessionRef.current = null
        sessionHairIdRef.current = null
      }
    },
    [clearReconnect, clearStatsPolling, resetMetrics, teardownConnection],
  )

  const sampleTransportStats = useCallback(async () => {
    const peerConnection = peerConnectionRef.current
    if (!peerConnection) {
      return
    }

    try {
      const report = await peerConnection.getStats()
      let selectedCandidatePair: RTCStats | null = null
      let outboundVideo: RTCStats | null = null
      let inboundVideo: RTCStats | null = null

      report.forEach((statsItem) => {
        if (statsItem.type === 'candidate-pair') {
          const isSelected =
            readStatBoolean(statsItem, 'selected') === true ||
            readStatBoolean(statsItem, 'nominated') === true
          const isSucceeded =
            (statsItem as RTCStats & Record<string, unknown>).state === 'succeeded'

          if (!selectedCandidatePair && (isSelected || isSucceeded)) {
            selectedCandidatePair = statsItem
          }
          return
        }

        if (
          statsItem.type === 'outbound-rtp' &&
          (statsItem as RTCStats & Record<string, unknown>).kind === 'video'
        ) {
          outboundVideo = statsItem
          return
        }

        if (
          statsItem.type === 'inbound-rtp' &&
          (statsItem as RTCStats & Record<string, unknown>).kind === 'video'
        ) {
          inboundVideo = statsItem
        }
      })

      const currentRoundTripTimeSeconds = selectedCandidatePair
        ? readStatNumber(selectedCandidatePair, 'currentRoundTripTime')
        : null
      const availableOutgoingBitrateBps = selectedCandidatePair
        ? readStatNumber(selectedCandidatePair, 'availableOutgoingBitrate')
        : null
      const outboundBytes = outboundVideo
        ? readStatNumber(outboundVideo, 'bytesSent')
        : null
      const inboundBytes = inboundVideo
        ? readStatNumber(inboundVideo, 'bytesReceived')
        : null
      const now = performance.now()
      const previous = lastStatsSampleRef.current

      let outboundBitrateKbps: number | null = null
      let inboundBitrateKbps: number | null = null

      if (previous.timestampMs != null) {
        const deltaMs = now - previous.timestampMs
        if (deltaMs > 0) {
          if (outboundBytes != null && previous.outboundBytes != null) {
            outboundBitrateKbps =
              ((outboundBytes - previous.outboundBytes) * 8) / deltaMs
          }
          if (inboundBytes != null && previous.inboundBytes != null) {
            inboundBitrateKbps =
              ((inboundBytes - previous.inboundBytes) * 8) / deltaMs
          }
        }
      }

      lastStatsSampleRef.current = {
        timestampMs: now,
        outboundBytes,
        inboundBytes,
      }

      transportSnapshotRef.current = {
        transportRoundTripTimeMs:
          currentRoundTripTimeSeconds != null
            ? currentRoundTripTimeSeconds * 1000
            : null,
        estimatedOneWayTransportMs:
          currentRoundTripTimeSeconds != null
            ? currentRoundTripTimeSeconds * 500
            : null,
        availableOutgoingBitrateKbps:
          availableOutgoingBitrateBps != null
            ? availableOutgoingBitrateBps / 1000
            : null,
        outboundBitrateKbps,
        inboundBitrateKbps,
        outboundFramesPerSecond: outboundVideo
          ? readStatNumber(outboundVideo, 'framesPerSecond')
          : null,
        inboundFramesPerSecond: inboundVideo
          ? readStatNumber(inboundVideo, 'framesPerSecond')
          : null,
        outboundFrameWidth: outboundVideo
          ? readStatNumber(outboundVideo, 'frameWidth')
          : null,
        outboundFrameHeight: outboundVideo
          ? readStatNumber(outboundVideo, 'frameHeight')
          : null,
        inboundFrameWidth: inboundVideo
          ? readStatNumber(inboundVideo, 'frameWidth')
          : null,
        inboundFrameHeight: inboundVideo
          ? readStatNumber(inboundVideo, 'frameHeight')
          : null,
      }

      setMetrics((previousMetrics) => ({
        ...previousMetrics,
        ...transportSnapshotRef.current,
      }))
    } catch (error) {
      console.warn('RTC getStats failed:', error)
    }
  }, [])

  const startStatsPolling = useCallback(() => {
    clearStatsPolling()
    void sampleTransportStats()
    statsTimerRef.current = window.setInterval(() => {
      void sampleTransportStats()
    }, RTC_STATS_POLL_INTERVAL_MS)
  }, [clearStatsPolling, sampleTransportStats])

  const scheduleReconnect = useCallback(
    (reason: string) => {
      if (
        reconnectingRef.current ||
        !latestEnabledRef.current ||
        !latestHairIdRef.current ||
        !latestStreamRef.current
      ) {
        return
      }

      reconnectingRef.current = true
      setError(reason)
      clearStatsPolling()
      teardownConnection(false)

      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null
        setReconnectVersion((value) => value + 1)
      }, RECONNECT_DELAY_MS)
    },
    [clearStatsPolling, teardownConnection],
  )

  const openSession = useCallback(
    async (nextHairId: number, localStream: MediaStream) => {
      const requestId = bootstrapRequestRef.current + 1
      bootstrapRequestRef.current = requestId
      resetRuntime({ clearSession: false })

      try {
        const nextBootstrap =
          sessionRef.current && sessionHairIdRef.current === nextHairId
            ? await postHairApplyResumeV2(
                sessionRef.current.applySessionId,
                deviceIdRef.current,
              )
            : await postHairApplyStartV2(nextHairId, deviceIdRef.current)

        if (bootstrapRequestRef.current !== requestId) {
          return
        }
        if (!nextBootstrap.rtc.enabled) {
          setError('RTC가 비활성화되어 있습니다.')
          return
        }

        const videoTracks = localStream.getVideoTracks()
        if (videoTracks.length === 0) {
          setError('카메라 비디오 트랙을 찾지 못했습니다.')
          return
        }

        const peerConnection = new RTCPeerConnection({
          iceServers: nextBootstrap.rtc.iceServers.map((server) => ({
            urls: server.urls,
            username: server.username ?? undefined,
            credential: server.credential ?? undefined,
          })),
          iceTransportPolicy: 'all',
        })
        const remoteMediaStream = new MediaStream()

        peerConnectionRef.current = peerConnection
        sessionRef.current = nextBootstrap
        sessionHairIdRef.current = nextHairId
        remoteStreamRef.current = remoteMediaStream
        manualCloseRef.current = false
        reconnectingRef.current = false
        setRemoteStream(remoteMediaStream)
        setConnectionState(peerConnection.connectionState)
        setError(null)
        startStatsPolling()

        peerConnection.addEventListener('connectionstatechange', () => {
          const nextState = peerConnection.connectionState
          setConnectionState(nextState)
          if (
            manualCloseRef.current ||
            (nextState !== 'failed' &&
              nextState !== 'disconnected' &&
              nextState !== 'closed')
          ) {
            return
          }
          scheduleReconnect('RTC 연결이 끊어졌습니다.')
        })

        peerConnection.addEventListener('track', (event) => {
          const currentRemoteStream = remoteStreamRef.current
          if (!currentRemoteStream) {
            return
          }
          currentRemoteStream.addTrack(event.track)
          setRemoteStream(new MediaStream(currentRemoteStream.getTracks()))
          event.track.addEventListener('ended', () => {
            currentRemoteStream.removeTrack(event.track)
            setRemoteStream(new MediaStream(currentRemoteStream.getTracks()))
          })
        })

        const dataChannel = peerConnection.createDataChannel('hairapply-events')
        dataChannelRef.current = dataChannel

        dataChannel.addEventListener('open', () => {
          setError(null)
        })

        dataChannel.addEventListener('close', () => {
          if (!manualCloseRef.current) {
            scheduleReconnect('RTC 데이터 채널이 닫혔습니다.')
          }
        })

        dataChannel.addEventListener('message', (event) => {
          try {
            const rawMessage = JSON.parse(String(event.data)) as unknown
            const message = parseInferenceMessage(rawMessage)
            const raw = stringifyDebugPayload(rawMessage)

            if (message.type === 'connected') {
              appendDebugLog({
                atIso: new Date().toISOString(),
                type: 'connected',
                summary: `connected node=${message.nodeId}`,
                raw,
              })
              return
            }

            if (message.type === 'heartbeat_ack') {
              appendDebugLog({
                atIso: new Date().toISOString(),
                type: 'heartbeat_ack',
                summary: 'heartbeat_ack',
                raw,
              })
              return
            }
            if (message.type === 'error') {
              setError(message.message)
              appendDebugLog({
                atIso: new Date().toISOString(),
                type: 'error',
                summary: `error ${message.code}: ${message.message}`,
                raw,
              })
              return
            }

            const serverProcessingMs = extractServerProcessingMs(rawMessage)
            lastServerProcessingMsRef.current = serverProcessingMs
            setAsset(message.asset)
            processedCountRef.current += 1

            if (lastAssetIdRef.current === message.asset.assetId) {
              stableAssetCountRef.current += 1
            } else {
              lastAssetIdRef.current = message.asset.assetId
              stableAssetCountRef.current = 1
            }

            if (
              !isRenderReadyRef.current &&
              processedCountRef.current >= REMOTE_READY_MIN_PROCESSED &&
              stableAssetCountRef.current >= REMOTE_READY_MIN_STABLE_ASSET
            ) {
              isRenderReadyRef.current = true
              setIsRenderReady(true)
            }

            const now = performance.now()
            if (lastProcessedAtRef.current != null) {
              const deltaMs = now - lastProcessedAtRef.current
              if (deltaMs > 0) {
                const nextFps = 1000 / deltaMs
                processedFpsEmaRef.current =
                  processedFpsEmaRef.current == null
                    ? nextFps
                    : processedFpsEmaRef.current * 0.8 + nextFps * 0.2
              }
            }
            lastProcessedAtRef.current = now

            setMetrics({
              inferenceRttMs: null,
              processedFps: processedFpsEmaRef.current,
              queueDepth: message.queueDepth,
              droppedPendingCount: message.droppedPendingCount,
              ...transportSnapshotRef.current,
              serverProcessingMs,
            })
            appendDebugLog({
              atIso: new Date().toISOString(),
              type: 'processed',
              summary: [
                `processed seq=${message.processedSeq}`,
                `queue=${message.queueDepth}`,
                `drop=${message.droppedPendingCount}`,
                serverProcessingMs != null
                  ? `server=${serverProcessingMs.toFixed(1)}ms`
                  : null,
                transportSnapshotRef.current.transportRoundTripTimeMs != null
                  ? `rtc_rtt=${transportSnapshotRef.current.transportRoundTripTimeMs.toFixed(1)}ms`
                  : null,
              ]
                .filter(Boolean)
                .join(' '),
              raw,
            })
          } catch (caught) {
            console.error('RTC data channel parse failed:', caught)
          }
        })

        for (const track of videoTracks) {
          const sender = peerConnection.addTrack(track, localStream)
          void configureRtcSender(sender)
        }

        const offer = await peerConnection.createOffer()
        await peerConnection.setLocalDescription(offer)
        await waitForIceGatheringComplete(peerConnection)

        const answer = await postRtcOffer({
          offerUrl: nextBootstrap.rtc.offerUrl,
          connectTicket: nextBootstrap.rtc.connectTicket,
          localDescription: peerConnection.localDescription ?? offer,
        })

        if (bootstrapRequestRef.current !== requestId) {
          return
        }

        await peerConnection.setRemoteDescription(answer)
        setError(null)
      } catch (caught) {
        if (bootstrapRequestRef.current !== requestId) {
          return
        }
        setError(
          caught instanceof Error ? caught.message : 'RTC 세션 시작 실패',
        )
        scheduleReconnect('RTC 세션 재시도 중')
      }
    },
    [appendDebugLog, resetRuntime, scheduleReconnect, startStatsPolling],
  )

  useEffect(() => {
    void reconnectVersion

    if (!enabled || !hairId || hairId <= 0 || !stream) {
      resetRuntime({ clearSession: true })
      return
    }

    void openSession(hairId, stream)

    return () => {
      bootstrapRequestRef.current += 1
      resetRuntime({ clearSession: false })
    }
  }, [enabled, hairId, openSession, reconnectVersion, resetRuntime, stream])

  return {
    isConnected:
      connectionState === 'connected' || connectionState === 'connecting',
    connectionState,
    remoteStream,
    asset,
    isRenderReady,
    error,
    metrics,
    debugLogs,
  }
}
