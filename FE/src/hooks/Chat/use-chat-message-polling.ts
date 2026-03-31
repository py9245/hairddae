import { useCallback, useEffect, useRef, useState } from 'react'

export type ChatPollingStatus = 'idle' | 'polling' | 'success' | 'error'

export type ChatPollingFetcherResult<TData> = {
  done?: boolean
  data?: TData | null
  message?: string | null
}

type UseChatMessagePollingArgs<TData> = {
  roomId: number | string | null
  enabled?: boolean
  pollIntervalMs?: number
  fetcher: (roomId: number | string) => Promise<ChatPollingFetcherResult<TData>>
}

export function useChatMessagePolling<TData>({
  roomId,
  enabled = true,
  pollIntervalMs = 5000,
  fetcher,
}: UseChatMessagePollingArgs<TData>) {
  const timerRef = useRef<number | null>(null)
  const inFlightRef = useRef(false)

  const [status, setStatus] = useState<ChatPollingStatus>('idle')
  const [data, setData] = useState<TData | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)

  const clearPolling = useCallback(() => {
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const stopPolling = useCallback(() => {
    clearPolling()
    inFlightRef.current = false
    setStatus((currentStatus) =>
      currentStatus === 'success' ? currentStatus : 'idle',
    )
  }, [clearPolling])

  const runPolling = useCallback(async () => {
    if (!enabled || roomId == null || inFlightRef.current) {
      return
    }

    inFlightRef.current = true

    try {
      const result = await fetcher(roomId)

      setData(result.data ?? null)
      setMessage(result.message ?? null)
      setError(null)
      setStatus(result.done ? 'success' : 'polling')

      if (result.done) {
        clearPolling()
        return
      }

      timerRef.current = window.setTimeout(() => {
        void runPolling()
      }, pollIntervalMs)
    } catch (caught) {
      const nextError =
        caught instanceof Error
          ? caught
          : new Error('채팅 메시지 조회에 실패했습니다.')

      setError(nextError)
      setMessage(nextError.message)
      setStatus('error')
      clearPolling()
    } finally {
      inFlightRef.current = false
    }
  }, [clearPolling, enabled, fetcher, pollIntervalMs, roomId])

  useEffect(() => {
    if (!enabled || roomId == null) {
      stopPolling()
      return
    }

    setStatus('polling')
    void runPolling()

    return () => {
      clearPolling()
    }
  }, [clearPolling, enabled, roomId, runPolling, stopPolling])

  useEffect(() => {
    return () => {
      clearPolling()
    }
  }, [clearPolling])

  return {
    status,
    data,
    message,
    error,
    isIdle: status === 'idle',
    isPolling: status === 'polling',
    isSuccess: status === 'success',
    isError: status === 'error',
    stopPolling,
  }
}
