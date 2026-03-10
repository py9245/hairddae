import { useCallback, useEffect, useRef, useState } from 'react'

type Point3D = {
  x: number
  y: number
  z: number
}

export type HairFramePayload = {
  user_id: string
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
  url: string
  enabled?: boolean
}

export function useHairWebSocket({
  url,
  enabled = true,
}: UseHairWebSocketArgs) {
  const wsRef = useRef<WebSocket | null>(null)

  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<HairWsMessage | null>(null)
  const [resultPng, setResultPng] = useState<string | null>(null)
  const [resultJson, setResultJson] = useState<Record<string, unknown> | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) return

    const ws = new WebSocket(url)
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
  }, [url, enabled])

  // const sendFrame = useCallback((payload: HairFramePayload) => {
  //   const ws = wsRef.current
  //   if (!ws || ws.readyState !== WebSocket.OPEN) return false

  //   try {
  //     ws.send(JSON.stringify(payload))
  //     return true
  //   } catch (err) {
  //     console.error('frame 전송 실패:', err)
  //     return false
  //   }
  // }, []


const sendFrame = useCallback(async (payload: HairFramePayload) => {
  try {
    const res = await fetch('http://localhost:8000/frame', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      console.error('frame 전송 실패:', res.status, res.statusText)
      return false
    }

    const data = await res.json()
    console.log('frame 응답:', data)
    return true
  } catch (err) {
    console.error('frame 전송 실패:', err)
    return false
  }
}, [])

  return {
    isConnected,
    lastMessage,
    resultPng,
    resultJson,
    error,
    sendFrame,
  }
}