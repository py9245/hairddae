import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  buildInferenceFeatureMessage,
  getOrCreateDeviceId,
  parseInferenceMessage,
  postHairApplyResumeV2,
  postHairApplyStartV2,
  postRtcOffer,
  type HairApplyV2Response,
  type InferenceAssetBundle,
} from '@/lib/Camera/inference'
import type { PoseAngles } from '@/lib/Camera/types'

type UseHairRtcSessionArgs = {
  enabled?: boolean
  hairId?: number | null
  pose?: PoseAngles | null
  landmarks?: NormalizedLandmark[] | null
  stream: MediaStream | null
  videoRef: React.RefObject<HTMLVideoElement | null>
}

type HairRtcMetrics = {
  inferenceRttMs: number | null
  processedFps: number | null
  queueDepth: number
  droppedPendingCount: number
}

const RECONNECT_DELAY_MS = 800
const ICE_GATHERING_TIMEOUT_MS = 8000
const MAX_INFLIGHT_FEATURES = 3
const REMOTE_READY_MIN_PROCESSED = 3
const REMOTE_READY_MIN_STABLE_ASSET = 2

type QueuedFeature = {
  payload: string
  seq: number
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
  pose,
  landmarks,
  stream,
  videoRef,
}: UseHairRtcSessionArgs) {
  const deviceIdRef = useRef<string>(getOrCreateDeviceId())
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null)
  const dataChannelRef = useRef<RTCDataChannel | null>(null)
  const sessionRef = useRef<HairApplyV2Response | null>(null)
  const sessionHairIdRef = useRef<number | null>(null)
  const inflightSeqsRef = useRef<number[]>([])
  const pendingFeatureRef = useRef<QueuedFeature | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const processedTimeoutRef = useRef<number | null>(null)
  const sequenceRef = useRef(0)
  const sentAtBySeqRef = useRef(new Map<number, number>())
  const lastProcessedAtRef = useRef<number | null>(null)
  const processedCountRef = useRef(0)
  const stableAssetCountRef = useRef(0)
  const lastAssetIdRef = useRef<string | null>(null)
  const rttEmaRef = useRef<number | null>(null)
  const processedFpsEmaRef = useRef<number | null>(null)
  const bootstrapRequestRef = useRef(0)
  const latestEnabledRef = useRef(enabled)
  const latestHairIdRef = useRef<number | null>(hairId ?? null)
  const latestStreamRef = useRef<MediaStream | null>(stream)
  const remoteStreamRef = useRef<MediaStream | null>(null)
  const reconnectingRef = useRef(false)
  const manualCloseRef = useRef(false)

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
  })

  latestEnabledRef.current = enabled
  latestHairIdRef.current = hairId ?? null
  latestStreamRef.current = stream

  const clearReconnect = useCallback(() => {
    if (reconnectTimerRef.current == null) {
      return
    }
    window.clearTimeout(reconnectTimerRef.current)
    reconnectTimerRef.current = null
  }, [])

  const clearProcessedTimeout = useCallback(() => {
    if (processedTimeoutRef.current == null) {
      return
    }
    window.clearTimeout(processedTimeoutRef.current)
    processedTimeoutRef.current = null
  }, [])

  const teardownConnection = useCallback(
    (manual: boolean) => {
      manualCloseRef.current = manual
      clearProcessedTimeout()

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
    },
    [clearProcessedTimeout],
  )

  const resetMetrics = useCallback(() => {
    inflightSeqsRef.current = []
    pendingFeatureRef.current = null
    sentAtBySeqRef.current.clear()
    lastProcessedAtRef.current = null
    processedCountRef.current = 0
    stableAssetCountRef.current = 0
    lastAssetIdRef.current = null
    rttEmaRef.current = null
    processedFpsEmaRef.current = null
    setIsRenderReady(false)
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

  const sendQueuedFeature = useCallback(
    (queuedFeature: QueuedFeature) => {
      const dataChannel = dataChannelRef.current
      if (!dataChannel || dataChannel.readyState !== 'open') {
        return false
      }

      dataChannel.send(queuedFeature.payload)
      inflightSeqsRef.current = [
        ...inflightSeqsRef.current,
        queuedFeature.seq,
      ].slice(-MAX_INFLIGHT_FEATURES)
      sentAtBySeqRef.current.set(queuedFeature.seq, performance.now())
      armProcessedTimeout()
      return true
    },
    [armProcessedTimeout],
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
      setError(reason === 'processed timeout' ? 'RTC 재연결 중' : reason)
      teardownConnection(false)

      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null
        setReconnectVersion((value) => value + 1)
      }, RECONNECT_DELAY_MS)
    },
    [teardownConnection],
  )

  const armProcessedTimeout = useCallback(() => {
    clearProcessedTimeout()
    const timeoutMs = sessionRef.current?.inference.processedTimeoutMs ?? 250
    processedTimeoutRef.current = window.setTimeout(() => {
      scheduleReconnect('processed timeout')
    }, timeoutMs)
  }, [clearProcessedTimeout, scheduleReconnect])

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
            const message = parseInferenceMessage(
              JSON.parse(String(event.data)) as unknown,
            )
            if (message.type === 'connected' || message.type === 'heartbeat_ack') {
              return
            }
            if (message.type === 'error') {
              clearProcessedTimeout()
              inflightSeqsRef.current = []
              pendingFeatureRef.current = null
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
              !isRenderReady &&
              processedCountRef.current >= REMOTE_READY_MIN_PROCESSED &&
              stableAssetCountRef.current >= REMOTE_READY_MIN_STABLE_ASSET
            ) {
              setIsRenderReady(true)
            }

            const now = performance.now()
            const sentAt = sentAtBySeqRef.current.get(message.processedSeq)
            if (sentAt != null) {
              sentAtBySeqRef.current.delete(message.processedSeq)
              const nextRtt = now - sentAt
              rttEmaRef.current =
                rttEmaRef.current == null
                  ? nextRtt
                  : rttEmaRef.current * 0.8 + nextRtt * 0.2
            }

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

            inflightSeqsRef.current = inflightSeqsRef.current.filter(
              (seq) => seq !== message.processedSeq,
            )
            if (
              inflightSeqsRef.current.length === 0 &&
              pendingFeatureRef.current == null
            ) {
              clearProcessedTimeout()
            } else {
              armProcessedTimeout()
            }
            setMetrics({
              inferenceRttMs: rttEmaRef.current,
              processedFps: processedFpsEmaRef.current,
              queueDepth:
                message.queueDepth +
                inflightSeqsRef.current.length +
                (pendingFeatureRef.current ? 1 : 0),
              droppedPendingCount: message.droppedPendingCount,
            })

            const pendingFeature = pendingFeatureRef.current
            if (pendingFeature && inflightSeqsRef.current.length < MAX_INFLIGHT_FEATURES) {
              pendingFeatureRef.current = null
              void sendQueuedFeature(pendingFeature)
            }
          } catch (caught) {
            console.error('RTC data channel parse failed:', caught)
          }
        })

        for (const track of videoTracks) {
          peerConnection.addTrack(track, localStream)
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
        setError(caught instanceof Error ? caught.message : 'RTC 세션 시작 실패')
        scheduleReconnect('RTC 세션 재시도 중')
      }
    },
    [armProcessedTimeout, clearProcessedTimeout, resetRuntime, scheduleReconnect],
  )

  useEffect(() => {
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

  useEffect(() => {
    if (!enabled || !hairId || hairId <= 0) {
      return
    }
    if (!pose || !landmarks || landmarks.length === 0) {
      return
    }

    const video = videoRef.current
    const session = sessionRef.current
    const dataChannel = dataChannelRef.current

    if (!video || !session || !dataChannel || dataChannel.readyState !== 'open') {
      return
    }
    if (video.videoWidth <= 0 || video.videoHeight <= 0) {
      return
    }

    sequenceRef.current += 1
    const feature = buildInferenceFeatureMessage({
      applySessionId: session.applySessionId,
      hairId,
      featureSchemaVersion: session.featureSchemaVersion,
      transformVersion: session.transformVersion,
      videoWidth: video.videoWidth,
      videoHeight: video.videoHeight,
      landmarks,
      pose,
      seq: sequenceRef.current,
    })
    const queuedFeature = {
      payload: JSON.stringify(feature),
      seq: feature.seq,
    } satisfies QueuedFeature

    if (inflightSeqsRef.current.length >= MAX_INFLIGHT_FEATURES) {
      pendingFeatureRef.current = queuedFeature
      return
    }

    void sendQueuedFeature(queuedFeature)
  }, [enabled, hairId, landmarks, pose, sendQueuedFeature, videoRef])

  return {
    isConnected:
      connectionState === 'connected' || connectionState === 'connecting',
    connectionState,
    remoteStream,
    asset,
    isRenderReady,
    error,
    metrics,
  }
}
