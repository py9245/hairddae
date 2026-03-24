import { useCallback, useEffect, useRef, useState } from 'react'

import {
  getOrCreateDeviceId,
  type HairApplyV2Response,
  postHairApplyResumeV2,
  postHairApplyStartV2,
  postRtcOffer,
  safeParseInferenceControlMessage,
} from '@/lib/Camera/inference'
import {
  RTC_SENDER_MAX_BITRATE,
  RTC_SENDER_MAX_FRAMERATE,
  RTC_STAGE_FPS,
  RTC_STAGE_HEIGHT,
  RTC_STAGE_MIRRORED,
  RTC_STAGE_WIDTH,
} from '@/lib/Camera/runtime'

type UseHairRtcSessionArgs = {
  enabled?: boolean
  hairId?: number | null
  datasetCode?: string | null
  stream: MediaStream | null
}

type StatsSnapshot = {
  timestampMs: number
  outboundBytesSent: number | null
  inboundFramesDecoded: number | null
}

type HairRtcMetrics = {
  senderFps: number | null
  senderBitrateKbps: number | null
  senderFrameWidth: number | null
  senderFrameHeight: number | null
  senderQualityLimitationReason: string | null
  receiverFps: number | null
  roundTripTimeMs: number | null
  heartbeatRttMs: number | null
  decodeMs: number | null
  trackingMs: number | null
  hairSegmentationMs: number | null
  hairAttenuationMs: number | null
  inferMs: number | null
  renderMs: number | null
  encodeMs: number | null
  e2eEstimateMs: number | null
  queueDepth: number
  droppedPendingCount: number
  packetsLost: number | null
}

type HairSelection = {
  hairId: number | null
  datasetCode: string | null
}

const RECONNECT_DELAY_MS = 800
const ICE_GATHERING_TIMEOUT_MS = 1500
const HEARTBEAT_INTERVAL_MS = 5000
const STATS_POLL_INTERVAL_MS = 1000
const RTC_SESSION_VERSION = 1
const RTC_DC_LOG_PREFIX = '[hair-rtc:datachannel]'

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
  datasetCode,
  stream,
}: UseHairRtcSessionArgs) {
  const deviceIdRef = useRef<string>(getOrCreateDeviceId())
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null)
  const dataChannelRef = useRef<RTCDataChannel | null>(null)
  const sessionRef = useRef<HairApplyV2Response | null>(null)
  const sessionStreamRef = useRef<MediaStream | null>(null)
  const remoteStreamRef = useRef<MediaStream | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const heartbeatTimerRef = useRef<number | null>(null)
  const statsTimerRef = useRef<number | null>(null)
  const bootstrapRequestRef = useRef(0)
  const heartbeatSentAtRef = useRef<number | null>(null)
  const statsSnapshotRef = useRef<StatsSnapshot | null>(null)
  const latestEnabledRef = useRef(enabled)
  const latestHairIdRef = useRef<number | null>(hairId ?? null)
  const latestDatasetCodeRef = useRef<string | null>(datasetCode ?? null)
  const latestStreamRef = useRef<MediaStream | null>(stream)
  const currentSelectionRef = useRef<HairSelection>({
    hairId: null,
    datasetCode: null,
  })
  const channelReadyRef = useRef(false)
  const manualCloseRef = useRef(false)
  const reconnectingRef = useRef(false)

  const [connectionState, setConnectionState] =
    useState<RTCPeerConnectionState>('new')
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null)
  const [isRenderReady, setIsRenderReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reconnectVersion, setReconnectVersion] = useState(0)
  const [appliedHairId, setAppliedHairId] = useState<number | null>(null)
  const [hasHelloApplied, setHasHelloApplied] = useState(false)
  const [metrics, setMetrics] = useState<HairRtcMetrics>({
    senderFps: null,
    senderBitrateKbps: null,
    senderFrameWidth: null,
    senderFrameHeight: null,
    senderQualityLimitationReason: null,
    receiverFps: null,
    roundTripTimeMs: null,
    heartbeatRttMs: null,
    decodeMs: null,
    trackingMs: null,
    hairSegmentationMs: null,
    hairAttenuationMs: null,
    inferMs: null,
    renderMs: null,
    encodeMs: null,
    e2eEstimateMs: null,
    queueDepth: 0,
    droppedPendingCount: 0,
    packetsLost: null,
  })

  latestEnabledRef.current = enabled
  latestHairIdRef.current = hairId ?? null
  latestDatasetCodeRef.current = datasetCode ?? null
  latestStreamRef.current = stream

  const clearReconnect = useCallback(() => {
    if (reconnectTimerRef.current == null) {
      return
    }
    window.clearTimeout(reconnectTimerRef.current)
    reconnectTimerRef.current = null
  }, [])

  const clearHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current == null) {
      return
    }
    window.clearInterval(heartbeatTimerRef.current)
    heartbeatTimerRef.current = null
  }, [])

  const clearStatsPolling = useCallback(() => {
    if (statsTimerRef.current == null) {
      return
    }
    window.clearInterval(statsTimerRef.current)
    statsTimerRef.current = null
  }, [])

  const sendControlMessage = useCallback((message: Record<string, unknown>) => {
    const dataChannel = dataChannelRef.current
    if (!dataChannel || dataChannel.readyState !== 'open') {
      return
    }
    console.info(`${RTC_DC_LOG_PREFIX} send`, message)
    dataChannel.send(JSON.stringify(message))
  }, [])

  const teardownConnection = useCallback(
    (manual: boolean) => {
      manualCloseRef.current = manual
      channelReadyRef.current = false
      clearHeartbeat()
      clearStatsPolling()

      dataChannelRef.current?.close()
      dataChannelRef.current = null

      peerConnectionRef.current?.close()
      peerConnectionRef.current = null
      sessionStreamRef.current = null
      currentSelectionRef.current = {
        hairId: null,
        datasetCode: null,
      }

      remoteStreamRef.current?.getTracks().forEach((track) => {
        track.stop()
      })
      remoteStreamRef.current = null
      setRemoteStream(null)
      setConnectionState('closed')
    },
    [clearHeartbeat, clearStatsPolling],
  )

  const resetRuntime = useCallback(
    ({ clearSession }: { clearSession: boolean }) => {
      clearReconnect()
      reconnectingRef.current = false
      teardownConnection(true)
      heartbeatSentAtRef.current = null
      statsSnapshotRef.current = null
      setIsRenderReady(false)
      setAppliedHairId(null)
      setHasHelloApplied(false)
      setError(null)
      setMetrics({
        senderFps: null,
        senderBitrateKbps: null,
        senderFrameWidth: null,
        senderFrameHeight: null,
        senderQualityLimitationReason: null,
        receiverFps: null,
        roundTripTimeMs: null,
        heartbeatRttMs: null,
        decodeMs: null,
        trackingMs: null,
        hairSegmentationMs: null,
        hairAttenuationMs: null,
        inferMs: null,
        renderMs: null,
        encodeMs: null,
        e2eEstimateMs: null,
        queueDepth: 0,
        droppedPendingCount: 0,
        packetsLost: null,
      })
      if (clearSession) {
        sessionRef.current = null
      }
    },
    [clearReconnect, teardownConnection],
  )

  const pollPeerConnectionStats = useCallback(async () => {
    const peerConnection = peerConnectionRef.current
    if (!peerConnection) {
      return
    }

    try {
      const report = await peerConnection.getStats()
      let outboundBytesSent: number | null = null
      let inboundFramesDecoded: number | null = null
      let senderFps: number | null = null
      let senderFrameWidth: number | null = null
      let senderFrameHeight: number | null = null
      let senderQualityLimitationReason: string | null = null
      let receiverFps: number | null = null
      let roundTripTimeMs: number | null = null
      let packetsLost: number | null = null
      let timestampMs = performance.now()

      report.forEach((entry) => {
        const value = entry as RTCStats & Record<string, unknown>
        const mediaType =
          typeof value.kind === 'string'
            ? value.kind
            : typeof value.mediaType === 'string'
              ? value.mediaType
              : null

        if (
          value.type === 'outbound-rtp' &&
          mediaType === 'video' &&
          value.isRemote !== true
        ) {
          if (typeof value.timestamp === 'number') {
            timestampMs = value.timestamp
          }
          if (typeof value.bytesSent === 'number') {
            outboundBytesSent = value.bytesSent
          }
          if (typeof value.framesPerSecond === 'number') {
            senderFps = value.framesPerSecond
          }
          if (typeof value.frameWidth === 'number') {
            senderFrameWidth = value.frameWidth
          }
          if (typeof value.frameHeight === 'number') {
            senderFrameHeight = value.frameHeight
          }
          if (typeof value.qualityLimitationReason === 'string') {
            senderQualityLimitationReason = value.qualityLimitationReason
          }
        }

        if (
          value.type === 'inbound-rtp' &&
          mediaType === 'video' &&
          value.isRemote !== true
        ) {
          if (typeof value.framesPerSecond === 'number') {
            receiverFps = value.framesPerSecond
          }
          if (typeof value.framesDecoded === 'number') {
            inboundFramesDecoded = value.framesDecoded
          }
          if (typeof value.packetsLost === 'number') {
            packetsLost = value.packetsLost
          }
        }

        if (
          value.type === 'remote-inbound-rtp' &&
          mediaType === 'video' &&
          typeof value.roundTripTime === 'number'
        ) {
          roundTripTimeMs = value.roundTripTime * 1000
          if (typeof value.packetsLost === 'number') {
            packetsLost = value.packetsLost
          }
        }

        if (
          roundTripTimeMs == null &&
          value.type === 'candidate-pair' &&
          typeof value.currentRoundTripTime === 'number' &&
          (value.state === 'succeeded' || value.nominated === true)
        ) {
          roundTripTimeMs = value.currentRoundTripTime * 1000
        }
      })

      let senderBitrateKbps: number | null = null
      const previousSnapshot = statsSnapshotRef.current
      if (
        previousSnapshot &&
        previousSnapshot.outboundBytesSent != null &&
        outboundBytesSent != null &&
        timestampMs > previousSnapshot.timestampMs
      ) {
        const elapsedSeconds =
          (timestampMs - previousSnapshot.timestampMs) / 1000
        if (elapsedSeconds > 0) {
          senderBitrateKbps =
            ((outboundBytesSent - previousSnapshot.outboundBytesSent) * 8) /
            elapsedSeconds /
            1000
        }
      }

      if (
        receiverFps == null &&
        previousSnapshot &&
        previousSnapshot.inboundFramesDecoded != null &&
        inboundFramesDecoded != null &&
        timestampMs > previousSnapshot.timestampMs
      ) {
        const elapsedSeconds =
          (timestampMs - previousSnapshot.timestampMs) / 1000
        if (elapsedSeconds > 0) {
          receiverFps =
            (inboundFramesDecoded - previousSnapshot.inboundFramesDecoded) /
            elapsedSeconds
        }
      }

      statsSnapshotRef.current = {
        timestampMs,
        outboundBytesSent,
        inboundFramesDecoded,
      }

      setMetrics((current) => ({
        ...current,
        senderFps: senderFps ?? current.senderFps,
        senderBitrateKbps: senderBitrateKbps ?? current.senderBitrateKbps,
        senderFrameWidth: senderFrameWidth ?? current.senderFrameWidth,
        senderFrameHeight: senderFrameHeight ?? current.senderFrameHeight,
        senderQualityLimitationReason:
          senderQualityLimitationReason ??
          current.senderQualityLimitationReason,
        receiverFps: receiverFps ?? current.receiverFps,
        roundTripTimeMs: roundTripTimeMs ?? current.roundTripTimeMs,
        packetsLost: packetsLost ?? current.packetsLost,
      }))
    } catch (caught) {
      console.warn('RTC stats polling failed:', caught)
    }
  }, [])

  const startStatsPolling = useCallback(() => {
    clearStatsPolling()
    void pollPeerConnectionStats()
    statsTimerRef.current = window.setInterval(() => {
      void pollPeerConnectionStats()
    }, STATS_POLL_INTERVAL_MS)
  }, [clearStatsPolling, pollPeerConnectionStats])

  const buildHelloMessage = useCallback(() => {
    const message: Record<string, unknown> = {
      type: 'hello',
      session_version: RTC_SESSION_VERSION,
      stage_width: RTC_STAGE_WIDTH,
      stage_height: RTC_STAGE_HEIGHT,
      fps: RTC_STAGE_FPS,
      mirrored: RTC_STAGE_MIRRORED,
    }

    if (latestHairIdRef.current != null) {
      message.hair_id = latestHairIdRef.current
    }
    if (latestDatasetCodeRef.current) {
      message.dataset_code = latestDatasetCodeRef.current
    }

    return message
  }, [])

  const buildSelectHairMessage = useCallback(
    (nextHairId: number, nextDatasetCode: string | null) => {
      const message: Record<string, unknown> = {
        type: 'select_hair',
        hair_id: nextHairId,
      }

      if (nextDatasetCode) {
        message.dataset_code = nextDatasetCode
      }

      return message
    },
    [],
  )

  const startHeartbeat = useCallback(() => {
    clearHeartbeat()
    heartbeatTimerRef.current = window.setInterval(() => {
      heartbeatSentAtRef.current = performance.now()
      sendControlMessage({
        type: 'heartbeat',
        ts_ms: Date.now(),
      })
    }, HEARTBEAT_INTERVAL_MS)
  }, [clearHeartbeat, sendControlMessage])

  const sendHairSelection = useCallback(
    (
      nextHairId: number,
      nextDatasetCode: string | null,
      options?: {
        force?: boolean
      },
    ) => {
      if (
        nextHairId <= 0 ||
        !channelReadyRef.current ||
        dataChannelRef.current?.readyState !== 'open'
      ) {
        return false
      }

      const force = options?.force === true
      const previousSelection = currentSelectionRef.current
      if (
        !force &&
        previousSelection.hairId === nextHairId &&
        previousSelection.datasetCode === nextDatasetCode
      ) {
        return true
      }

      currentSelectionRef.current = {
        hairId: nextHairId,
        datasetCode: nextDatasetCode,
      }
      setAppliedHairId(null)
      setIsRenderReady(false)
      sendControlMessage(buildSelectHairMessage(nextHairId, nextDatasetCode))
      return true
    },
    [buildSelectHairMessage, sendControlMessage],
  )

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
      teardownConnection(false)

      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null
        setReconnectVersion((value) => value + 1)
      }, RECONNECT_DELAY_MS)
    },
    [teardownConnection],
  )

  const openSession = useCallback(
    async (
      nextHairId: number,
      _nextDatasetCode: string | null,
      localStream: MediaStream,
    ) => {
      const requestId = bootstrapRequestRef.current + 1
      bootstrapRequestRef.current = requestId
      resetRuntime({ clearSession: false })

      try {
        const nextBootstrap = sessionRef.current
          ? await postHairApplyResumeV2(
              sessionRef.current.applySessionId,
              deviceIdRef.current,
            )
          : await postHairApplyStartV2(nextHairId, deviceIdRef.current)

        if (bootstrapRequestRef.current !== requestId) {
          return
        }

        if (!nextBootstrap.rtc.enabled) {
          setError('RTC is disabled.')
          return
        }

        const videoTracks = localStream.getVideoTracks()
        if (videoTracks.length === 0) {
          setError('Camera video track not found.')
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
        sessionStreamRef.current = localStream
        remoteStreamRef.current = remoteMediaStream
        reconnectingRef.current = false
        manualCloseRef.current = false
        channelReadyRef.current = false
        setRemoteStream(remoteMediaStream)
        setConnectionState(peerConnection.connectionState)
        setError(null)

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
          scheduleReconnect('RTC connection lost.')
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

        const dataChannel = peerConnection.createDataChannel('control')
        dataChannelRef.current = dataChannel

        dataChannel.addEventListener('open', () => {
          setError(null)
          sendControlMessage(buildHelloMessage())
        })

        dataChannel.addEventListener('close', () => {
          channelReadyRef.current = false
          if (!manualCloseRef.current) {
            scheduleReconnect('RTC data channel closed.')
          }
        })

        dataChannel.addEventListener('message', (event) => {
          try {
            const rawPayload = JSON.parse(String(event.data)) as unknown
            const message = safeParseInferenceControlMessage(rawPayload)
            if (!message) {
              console.warn(`${RTC_DC_LOG_PREFIX} recv parse-failed`, rawPayload)
              return
            }
            console.info(`${RTC_DC_LOG_PREFIX} recv`, message)

            if (message.type === 'connected') {
              channelReadyRef.current = true
              setError(null)
              startHeartbeat()
              if (
                latestHairIdRef.current != null &&
                latestHairIdRef.current > 0
              ) {
                sendHairSelection(
                  latestHairIdRef.current,
                  latestDatasetCodeRef.current,
                  { force: true },
                )
              }
              return
            }

            if (message.type === 'hair_applied') {
              setAppliedHairId(message.hairId)
              setHasHelloApplied(message.source === 'hello')
              setIsRenderReady(true)
              return
            }

            if (message.type === 'heartbeat_ack') {
              const sentAt = heartbeatSentAtRef.current
              if (sentAt != null) {
                setMetrics((current) => ({
                  ...current,
                  heartbeatRttMs: performance.now() - sentAt,
                }))
              }
              heartbeatSentAtRef.current = null
              return
            }

            if (message.type === 'stats') {
              setMetrics((current) => ({
                ...current,
                queueDepth: message.queueDepth,
                droppedPendingCount: message.droppedPendingCount,
                decodeMs: message.decodeMs ?? current.decodeMs,
                trackingMs: message.trackingMs ?? current.trackingMs,
                hairSegmentationMs:
                  message.hairSegmentationMs ?? current.hairSegmentationMs,
                hairAttenuationMs:
                  message.hairAttenuationMs ?? current.hairAttenuationMs,
                inferMs: message.inferMs ?? current.inferMs,
                renderMs: message.renderMs ?? current.renderMs,
                encodeMs: message.encodeMs ?? current.encodeMs,
                e2eEstimateMs: message.e2eEstimateMs ?? current.e2eEstimateMs,
              }))
              return
            }

            if (message.type === 'error') {
              setError(message.message)
            }
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
        startStatsPolling()
      } catch (caught) {
        if (bootstrapRequestRef.current !== requestId) {
          return
        }
        setError(
          caught instanceof Error ? caught.message : 'RTC session start failed',
        )
        scheduleReconnect('Retrying RTC session')
      }
    },
    [
      buildHelloMessage,
      resetRuntime,
      scheduleReconnect,
      sendHairSelection,
      sendControlMessage,
      startHeartbeat,
      startStatsPolling,
    ],
  )

  useEffect(() => {
    void reconnectVersion

    if (!enabled || !hairId || hairId <= 0 || !stream) {
      resetRuntime({ clearSession: true })
      return
    }

    const hasActiveConnection =
      peerConnectionRef.current != null &&
      peerConnectionRef.current.connectionState !== 'closed' &&
      dataChannelRef.current != null &&
      dataChannelRef.current.readyState !== 'closed' &&
      sessionStreamRef.current === stream

    if (!hasActiveConnection) {
      void openSession(hairId, datasetCode ?? null, stream)
    }
  }, [
    datasetCode,
    enabled,
    hairId,
    openSession,
    reconnectVersion,
    resetRuntime,
    stream,
  ])

  useEffect(() => {
    if (
      !enabled ||
      !hairId ||
      hairId <= 0 ||
      !stream ||
      reconnectingRef.current
    ) {
      return
    }

    void sendHairSelection(hairId, datasetCode ?? null)
  }, [datasetCode, enabled, hairId, sendHairSelection, stream])

  useEffect(() => {
    return () => {
      bootstrapRequestRef.current += 1
      resetRuntime({ clearSession: false })
    }
  }, [resetRuntime])

  return {
    isConnected:
      connectionState === 'connected' || connectionState === 'connecting',
    connectionState,
    remoteStream,
    isRenderReady,
    error,
    appliedHairId,
    hasHelloApplied,
    metrics,
  }
}
