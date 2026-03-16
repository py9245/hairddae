import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  buildInferenceFeatureMessage,
  getOrCreateDeviceId,
  INFERENCE_WS_PROTOCOL,
  type InferenceAssetBundle,
  parseInferenceMessage,
  postHairApplyResumeV2,
  postHairApplyStartV2,
  type HairApplyV2Response,
} from '@/lib/Camera/inference'
import type { PoseAngles } from '@/lib/Camera/types'

type UseHairInferenceSessionArgs = {
  enabled?: boolean
  hairId?: number | null
  pose?: PoseAngles | null
  landmarks?: NormalizedLandmark[] | null
  videoRef: React.RefObject<HTMLVideoElement | null>
}

type HairInferenceMetrics = {
  inferenceRttMs: number | null
  processedFps: number | null
  queueDepth: number
  droppedPendingCount: number
}

const RECONNECT_DELAY_MS = 500

export function useHairInferenceSession({
  enabled = true,
  hairId,
  pose,
  landmarks,
  videoRef,
}: UseHairInferenceSessionArgs) {
  const deviceIdRef = useRef<string>(getOrCreateDeviceId())
  const wsRef = useRef<WebSocket | null>(null)
  const sessionRef = useRef<HairApplyV2Response | null>(null)
  const inflightSeqRef = useRef<number | null>(null)
  const pendingFeatureRef = useRef<string | null>(null)
  const sequenceRef = useRef(0)
  const processedTimeoutRef = useRef<number | null>(null)
  const heartbeatTimerRef = useRef<number | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const reconnectingRef = useRef(false)
  const manualCloseRef = useRef(false)
  const bootstrapRequestRef = useRef(0)
  const latestHairIdRef = useRef<number | null>(hairId ?? null)
  const latestEnabledRef = useRef(enabled)
  const lastActivityAtRef = useRef(performance.now())
  const sentAtBySeqRef = useRef(new Map<number, number>())
  const lastProcessedAtRef = useRef<number | null>(null)
  const rttEmaRef = useRef<number | null>(null)
  const processedFpsEmaRef = useRef<number | null>(null)

  const [isConnected, setIsConnected] = useState(false)
  const [asset, setAsset] = useState<InferenceAssetBundle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [metrics, setMetrics] = useState<HairInferenceMetrics>({
    inferenceRttMs: null,
    processedFps: null,
    queueDepth: 0,
    droppedPendingCount: 0,
  })

  latestHairIdRef.current = hairId ?? null
  latestEnabledRef.current = enabled

  const clearProcessedTimeout = useCallback(() => {
    if (processedTimeoutRef.current == null) return
    window.clearTimeout(processedTimeoutRef.current)
    processedTimeoutRef.current = null
  }, [])

  const clearHeartbeatTimer = useCallback(() => {
    if (heartbeatTimerRef.current == null) return
    window.clearInterval(heartbeatTimerRef.current)
    heartbeatTimerRef.current = null
  }, [])

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current == null) return
    window.clearTimeout(reconnectTimerRef.current)
    reconnectTimerRef.current = null
  }, [])

  const closeSocket = useCallback(() => {
    const ws = wsRef.current
    if (!ws) return
    manualCloseRef.current = true
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close()
    }
    wsRef.current = null
  }, [])

  const resetRuntime = useCallback(() => {
    clearProcessedTimeout()
    clearHeartbeatTimer()
    clearReconnectTimer()
    closeSocket()
    inflightSeqRef.current = null
    pendingFeatureRef.current = null
    reconnectingRef.current = false
    sentAtBySeqRef.current.clear()
    lastProcessedAtRef.current = null
    rttEmaRef.current = null
    processedFpsEmaRef.current = null
    setIsConnected(false)
    setMetrics({
      inferenceRttMs: null,
      processedFps: null,
      queueDepth: 0,
      droppedPendingCount: 0,
    })
  }, [clearHeartbeatTimer, clearProcessedTimeout, clearReconnectTimer, closeSocket])

  const scheduleReconnect = useCallback(async (reason: string) => {
    if (reconnectingRef.current) return
    if (!latestEnabledRef.current || !latestHairIdRef.current) return

    reconnectingRef.current = true
    setIsConnected(false)
    clearProcessedTimeout()
    clearHeartbeatTimer()
    clearReconnectTimer()
    closeSocket()

    reconnectTimerRef.current = window.setTimeout(async () => {
      reconnectTimerRef.current = null

      try {
        const currentSession = sessionRef.current
        const nextBootstrap = currentSession
          ? await postHairApplyResumeV2(
              currentSession.applySessionId,
              deviceIdRef.current,
            )
          : await postHairApplyStartV2(
              latestHairIdRef.current as number,
              deviceIdRef.current,
            )

        sessionRef.current = nextBootstrap
        setError(null)
        reconnectingRef.current = false
        manualCloseRef.current = false
        const ws = new WebSocket(nextBootstrap.inference.wsUrl, [
          INFERENCE_WS_PROTOCOL,
          `ticket.${nextBootstrap.inference.connectTicket}`,
        ])
        wsRef.current = ws

        ws.onopen = () => {
          setIsConnected(true)
          setError(null)
          lastActivityAtRef.current = performance.now()

          clearHeartbeatTimer()
          heartbeatTimerRef.current = window.setInterval(() => {
            const openSocket = wsRef.current
            const activeSession = sessionRef.current
            if (
              !openSocket ||
              openSocket.readyState !== WebSocket.OPEN ||
              !activeSession
            ) {
              return
            }

            const now = performance.now()
            if (
              now - lastActivityAtRef.current <
              activeSession.inference.heartbeatIntervalMs
            ) {
              return
            }

            openSocket.send(
              JSON.stringify({
                type: 'heartbeat',
                apply_session_id: activeSession.applySessionId,
                ts_ms: Date.now(),
              }),
            )
          }, Math.max(1000, nextBootstrap.inference.heartbeatIntervalMs))
        }

        ws.onmessage = (event) => {
          lastActivityAtRef.current = performance.now()

          try {
            const message = parseInferenceMessage(
              JSON.parse(event.data) as unknown,
            )

            if (message.type === 'connected') {
              return
            }

            if (message.type === 'heartbeat_ack') {
              return
            }

            if (message.type === 'error') {
              setError(message.message)
              clearProcessedTimeout()
              inflightSeqRef.current = null
              return
            }

            clearProcessedTimeout()
            inflightSeqRef.current = null
            setAsset(message.asset)
            setError(message.overloaded ? '서버가 혼잡합니다.' : null)

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

            setMetrics({
              inferenceRttMs: rttEmaRef.current,
              processedFps: processedFpsEmaRef.current,
              queueDepth: message.queueDepth,
              droppedPendingCount: message.droppedPendingCount,
            })

            const pendingFeature = pendingFeatureRef.current
            const currentSocket = wsRef.current
            if (
              pendingFeature &&
              currentSocket &&
              currentSocket.readyState === WebSocket.OPEN
            ) {
              pendingFeatureRef.current = null
              currentSocket.send(pendingFeature)
              const parsed = JSON.parse(pendingFeature) as { seq: number }
              inflightSeqRef.current = parsed.seq
              sentAtBySeqRef.current.set(parsed.seq, performance.now())
              const timeoutMs =
                sessionRef.current?.inference.processedTimeoutMs ?? 250
              processedTimeoutRef.current = window.setTimeout(() => {
                void scheduleReconnect('processed timeout')
              }, timeoutMs)
            }
          } catch (caught) {
            console.error('inference ws parse failed:', caught)
          }
        }

        ws.onerror = () => {
          setError('인퍼런스 웹소켓 오류')
        }

        ws.onclose = () => {
          clearProcessedTimeout()
          clearHeartbeatTimer()
          setIsConnected(false)
          wsRef.current = null

          if (manualCloseRef.current || !latestEnabledRef.current) {
            manualCloseRef.current = false
            reconnectingRef.current = false
            return
          }

          void scheduleReconnect(reason)
        }
      } catch (caught) {
        reconnectingRef.current = false
        setError(caught instanceof Error ? caught.message : '재연결 실패')
        void scheduleReconnect(reason)
      }
    }, RECONNECT_DELAY_MS)
  }, [
    clearHeartbeatTimer,
    clearProcessedTimeout,
    clearReconnectTimer,
    closeSocket,
  ])

  const openSession = useCallback(async (nextHairId: number) => {
    const requestId = bootstrapRequestRef.current + 1
    bootstrapRequestRef.current = requestId
    resetRuntime()
    setAsset(null)
    setError(null)

    try {
      const bootstrap = await postHairApplyStartV2(nextHairId, deviceIdRef.current)
      if (bootstrapRequestRef.current !== requestId) {
        return
      }

      sessionRef.current = bootstrap
      reconnectingRef.current = false
      manualCloseRef.current = false

      const ws = new WebSocket(bootstrap.inference.wsUrl, [
        INFERENCE_WS_PROTOCOL,
        `ticket.${bootstrap.inference.connectTicket}`,
      ])
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        setError(null)
        lastActivityAtRef.current = performance.now()

        clearHeartbeatTimer()
        heartbeatTimerRef.current = window.setInterval(() => {
          const openSocket = wsRef.current
          const activeSession = sessionRef.current
          if (
            !openSocket ||
            openSocket.readyState !== WebSocket.OPEN ||
            !activeSession
          ) {
            return
          }

          const now = performance.now()
          if (
            now - lastActivityAtRef.current <
            activeSession.inference.heartbeatIntervalMs
          ) {
            return
          }

          openSocket.send(
            JSON.stringify({
              type: 'heartbeat',
              apply_session_id: activeSession.applySessionId,
              ts_ms: Date.now(),
            }),
          )
        }, Math.max(1000, bootstrap.inference.heartbeatIntervalMs))
      }

      ws.onmessage = (event) => {
        lastActivityAtRef.current = performance.now()

        try {
          const message = parseInferenceMessage(
            JSON.parse(event.data) as unknown,
          )

          if (message.type === 'connected') {
            return
          }

          if (message.type === 'heartbeat_ack') {
            return
          }

          if (message.type === 'error') {
            setError(message.message)
            clearProcessedTimeout()
            inflightSeqRef.current = null
            return
          }

          clearProcessedTimeout()
          inflightSeqRef.current = null
          setAsset(message.asset)
          setError(message.overloaded ? '서버가 혼잡합니다.' : null)

          const pendingFeature = pendingFeatureRef.current
          const currentSocket = wsRef.current
          if (
            pendingFeature &&
            currentSocket &&
            currentSocket.readyState === WebSocket.OPEN
          ) {
            pendingFeatureRef.current = null
            currentSocket.send(pendingFeature)
            const parsed = JSON.parse(pendingFeature) as { seq: number }
            inflightSeqRef.current = parsed.seq
            const timeoutMs =
              sessionRef.current?.inference.processedTimeoutMs ?? 250
            processedTimeoutRef.current = window.setTimeout(() => {
              void scheduleReconnect('processed timeout')
            }, timeoutMs)
          }
        } catch (caught) {
          console.error('inference ws parse failed:', caught)
        }
      }

      ws.onerror = () => {
        setError('인퍼런스 웹소켓 오류')
      }

      ws.onclose = () => {
        clearProcessedTimeout()
        clearHeartbeatTimer()
        setIsConnected(false)
        wsRef.current = null

        if (manualCloseRef.current || !latestEnabledRef.current) {
          manualCloseRef.current = false
          return
        }

        void scheduleReconnect('socket closed')
      }
    } catch (caught) {
      if (bootstrapRequestRef.current !== requestId) {
        return
      }
      setError(caught instanceof Error ? caught.message : '세션 시작 실패')
    }
  }, [
    clearHeartbeatTimer,
    clearProcessedTimeout,
    resetRuntime,
    scheduleReconnect,
  ])

  useEffect(() => {
    if (!enabled || !hairId || hairId <= 0) {
      sessionRef.current = null
      setAsset(null)
      setError(null)
      resetRuntime()
      return
    }

    void openSession(hairId)

    return () => {
      bootstrapRequestRef.current += 1
      resetRuntime()
    }
  }, [enabled, hairId, openSession, resetRuntime])

  useEffect(() => {
    if (!enabled || !hairId || hairId <= 0) return
    if (!pose || !landmarks || landmarks.length === 0) return

    const video = videoRef.current
    const session = sessionRef.current
    const ws = wsRef.current

    if (!video || !session || !ws || ws.readyState !== WebSocket.OPEN) {
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
    const payload = JSON.stringify(feature)
    lastActivityAtRef.current = performance.now()

    if (inflightSeqRef.current != null) {
      pendingFeatureRef.current = payload
      return
    }

    ws.send(payload)
    inflightSeqRef.current = feature.seq
    sentAtBySeqRef.current.set(feature.seq, performance.now())
    while (sentAtBySeqRef.current.size > 8) {
      const oldestKey = sentAtBySeqRef.current.keys().next().value
      if (oldestKey == null) {
        break
      }
      sentAtBySeqRef.current.delete(oldestKey)
    }
    clearProcessedTimeout()
    processedTimeoutRef.current = window.setTimeout(() => {
      void scheduleReconnect('processed timeout')
    }, session.inference.processedTimeoutMs)
  }, [
    clearProcessedTimeout,
    enabled,
    hairId,
    landmarks,
    pose,
    scheduleReconnect,
    videoRef,
  ])

  return {
    isConnected,
    asset,
    error,
    metrics,
    applySessionId: sessionRef.current?.applySessionId ?? null,
  }
}
