import { useCallback, useEffect, useRef, useState } from 'react'

export type HairWebSocketMessage =
  | {
      type?: 'connected'
      message?: string
      code?: number
      data?: {
        endpoint: string
      }
    }
  | {
      type?: 'pong'
      message?: string
      code?: number
      data?: null
    }
  | {
      type?: 'status'
      message?: string
      code?: number
      data?: {
        code: number
        message: string
        applySessionId: string
        jobType: string
        status: string
        hairID?: number
        completedAt?: string | null
      }
    }
  | {
      type?: 'error'
      message?: string
      code?: number
      data?: null
    }

type UseHairWebSocketArgs = {
  enabled?: boolean
}

const WS_URL = 'home/hairapply/'

function resolveWebSocketUrl() {
  if (typeof window === 'undefined') return null

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/${WS_URL.replace(/^\/+/, '')}`
}

export function useHairWebSocket({
  enabled = true,
}: UseHairWebSocketArgs = {}) {
  const wsRef = useRef<WebSocket | null>(null)

  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<HairWebSocketMessage | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) return
    const wsUrl = resolveWebSocketUrl()
    if (!wsUrl) {
      setError('웹소켓 URL을 구성할 수 없습니다.')
      return
    }

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      setError(null)
    }

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as HairWebSocketMessage
        setLastMessage(parsed)

        if ('message' in parsed && parsed.message) {
          setError(parsed.type === 'error' ? parsed.message : null)
        }
      } catch (err) {
        console.error('ws message parse failed:', err)
      }
    }

    ws.onerror = () => {
      setError('websocket error')
    }

    ws.onclose = () => {
      setIsConnected(false)
      wsRef.current = null
    }

    return () => {
      ws.close()
      wsRef.current = null
      setIsConnected(false)
    }
  }, [enabled])

  const sendJson = useCallback((payload: Record<string, unknown>) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return false

    try {
      ws.send(JSON.stringify(payload))
      return true
    } catch (err) {
      console.error('frame 전송 실패:', err)
      return false
    }
  }, [])

  const ping = useCallback(() => sendJson({ type: 'ping' }), [sendJson])

  const requestStatus = useCallback(
    (
      accessToken: string,
      applySessionId: string,
      type: 'status' | 'subscribe' = 'subscribe',
    ) =>
      sendJson({
        type,
        accessToken,
        applySessionId,
      }),
    [sendJson],
  )

  return {
    isConnected,
    lastMessage,
    error,
    ping,
    requestStatus,
  }
}
