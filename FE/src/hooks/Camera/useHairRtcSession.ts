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

type UseHairRtcSessionArgs = {
  enabled?: boolean
  hairId?: number | null
  stream: MediaStream | null
  senderConfig?: {
    maxBitrate: number
    maxFramerate: number
  }
}

type HairRtcMetrics = {
  inferenceRttMs: number | null
  processedFps: number | null
  queueDepth: number
  droppedPendingCount: number
}

const RECONNECT_DELAY_MS = 800
const ICE_GATHERING_TIMEOUT_MS = 1500
const REMOTE_READY_MIN_PROCESSED = 1
const REMOTE_READY_MIN_STABLE_ASSET = 1

async function configureRtcSender(
  sender: RTCRtpSender,
  senderConfig: NonNullable<UseHairRtcSessionArgs['senderConfig']>,
) {
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
    maxBitrate: senderConfig.maxBitrate,
    maxFramerate: senderConfig.maxFramerate,
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
  senderConfig = {
    maxBitrate: 8_000_000,
    maxFramerate: 15,
  },
}: UseHairRtcSessionArgs) {
  const deviceIdRef = useRef<string>(getOrCreateDeviceId())
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null)
  const dataChannelRef = useRef<RTCDataChannel | null>(null)
  const sessionRef = useRef<HairApplyV2Response | null>(null)
  const sessionHairIdRef = useRef<number | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const lastProcessedAtRef = useRef<number | null>(null)
  const processedCountRef = useRef(0)
  const stableAssetCountRef = useRef(0)
  const lastAssetIdRef = useRef<string | null>(null)
  const processedFpsEmaRef = useRef<number | null>(null)
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
  const [isAnswerReady, setIsAnswerReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reconnectVersion, setReconnectVersion] = useState(0)
  const [metrics, setMetrics] = useState<HairRtcMetrics>({
    inferenceRttMs: null,
    processedFps: null,
    queueDepth: 0,
    droppedPendingCount: 0,
  })

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
    setIsRenderReady(false)
    setIsAnswerReady(false)
    setMetrics({
      inferenceRttMs: null,
      processedFps: null,
      queueDepth: 0,
      droppedPendingCount: 0,
    })
  }, [])

  const resetRuntime = useCallback(
    ({ clearSession }: { clearSession: boolean }) => {
      clearReconnect()
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
    [clearReconnect, resetMetrics, teardownConnection],
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
        sessionHairIdRef.current = nextHairId
        remoteStreamRef.current = remoteMediaStream
        manualCloseRef.current = false
        reconnectingRef.current = false
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

        const dataChannel = peerConnection.createDataChannel('hairapply-events')
        dataChannelRef.current = dataChannel

        dataChannel.addEventListener('open', () => {
          setError(null)
        })

        dataChannel.addEventListener('close', () => {
          if (!manualCloseRef.current) {
            scheduleReconnect('RTC data channel closed.')
          }
        })

        dataChannel.addEventListener('message', (event) => {
          try {
            const message = parseInferenceMessage(
              JSON.parse(String(event.data)) as unknown,
            )
            if (
              message.type === 'connected' ||
              message.type === 'heartbeat_ack'
            ) {
              return
            }
            if (message.type === 'error') {
              setError(message.message)
              return
            }

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
            })
          } catch (caught) {
            console.error('RTC data channel parse failed:', caught)
          }
        })

        for (const track of videoTracks) {
          const sender = peerConnection.addTrack(track, localStream)
          void configureRtcSender(sender, senderConfig)
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
        setIsAnswerReady(true)
        setError(null)
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
    [resetRuntime, scheduleReconnect, senderConfig],
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
    isAnswerReady,
    error,
    metrics,
  }
}
