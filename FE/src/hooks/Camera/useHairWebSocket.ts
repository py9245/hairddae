import { useCallback, useEffect, useRef, useState } from 'react'

type Point3D = {
  x: number
  y: number
  z: number
}

type Pose = {
  yaw: number
  pitch: number
  roll: number
}

export type HairFramePayload = {
  user_id: string
  apply_session_id: string
  frame_id: number
  camera: {
    w: number
    h: number
  }
  angle_hash: number
  angle: {
    pitch: number
    yaw: number
    roll: number
  }
  forehead: Point3D
  landmark: Point3D[]
}

export type HairWsResult = {
  type?: 'result'
  png?: string
  json?: Record<string, unknown>
  frame_id?: number
  hair_id?: number
}

export type HairWsError = {
  type?: 'error'
  message?: string
}

type HairWsMessage = HairWsResult | HairWsError

type UseHairWebSocketArgs = {
  enabled?: boolean
  applySessionId?: string | null
  pose?: Pose | null
  landmarks?: Point3D[] | null
  selectedHairId?: number
}

const WS_BASE_URL = 'home/hairapply/'

function makeAngleHash(pose: Pose) {
  return Number(
    `${Math.round(pose.pitch)}${Math.round(pose.yaw)}${Math.round(pose.roll)}`,
  )
}

export function useHairWebSocket({
  enabled = true,
  applySessionId,
  pose,
  landmarks,
}: UseHairWebSocketArgs = {}) {
  const wsRef = useRef<WebSocket | null>(null)
  const frameIdRef = useRef(0)
  const lastSentAtRef = useRef(0)

  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<HairWsMessage | null>(null)
  const [resultPng, setResultPng] = useState<string | null>(null)
  const [resultJson, setResultJson] = useState<Record<string, unknown> | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) return
    if (!applySessionId) return

    if (!WS_BASE_URL) {
      setError('VITE_WS_URL이 설정되지 않았습니다.')
      return
    }

    const wsUrl = `${WS_BASE_URL}${applySessionId}/`
    console.log('WS_URL:', wsUrl)

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      setError(null)
    }

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as HairWsMessage
        setLastMessage(parsed)

        if ('message' in parsed && parsed.message) {
          setError(parsed.message)
        }

        if ('png' in parsed && parsed.png) {
          setResultPng(parsed.png)
        }

        if ('json' in parsed && parsed.json) {
          setResultJson(parsed.json)
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
  }, [enabled, applySessionId])

  const sendFrame = useCallback(
    (payload: Omit<HairFramePayload, 'apply_session_id'>) => {
      const ws = wsRef.current
      if (!ws || ws.readyState !== WebSocket.OPEN) return false
      if (!applySessionId) return false

      try {
        ws.send(
          JSON.stringify({
            ...payload,
            apply_session_id: applySessionId,
          }),
        )
        return true
      } catch (err) {
        console.error('frame 전송 실패:', err)
        return false
      }
    },
    [applySessionId],
  )

  useEffect(() => {
    if (!isConnected) return
    if (!applySessionId) return
    if (!pose) return
    if (!landmarks || landmarks.length === 0) return

    const forehead = landmarks[10]
    if (!forehead) return

    const now = performance.now()
    if (now - lastSentAtRef.current < 100) return
    lastSentAtRef.current = now

    frameIdRef.current += 1

    sendFrame({
      user_id: 'user-123',
      frame_id: frameIdRef.current,
      camera: {
        w: 430,
        h: 932,
      },
      angle_hash: makeAngleHash(pose),
      angle: {
        pitch: pose.pitch,
        yaw: pose.yaw,
        roll: pose.roll,
      },
      forehead,
      landmark: landmarks,
    })
  }, [isConnected, applySessionId, pose, landmarks, sendFrame])

  return {
    isConnected,
    lastMessage,
    resultPng,
    resultJson,
    error,
    sendFrame,
  }
}
