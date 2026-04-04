import { useCallback, useEffect, useRef, useState } from 'react'

export type DesignerPollingStatus = 'idle' | 'polling' | 'success' | 'error'

export type DesignerPollingFetcherResult<TData> = {
  done: boolean
  data?: TData | null
  message?: string | null
}

type UseDesignerPollingArgs<TData> = {
  enabled?: boolean
  pollIntervalMs?: number
  fetcher: (designerId: number) => Promise<DesignerPollingFetcherResult<TData>>
}

export function useDesignerPolling<TData>({
  enabled = true,
  pollIntervalMs = 3000,
  fetcher,
}: UseDesignerPollingArgs<TData>) {
  const timerRef = useRef<number | null>(null)
  const inFlightRef = useRef(false)

  const [designerId, setDesignerId] = useState<number | null>(null)
  const [status, setStatus] = useState<DesignerPollingStatus>('idle')
  const [data, setData] = useState<TData | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)

  const clearPolling = useCallback(() => {
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const reset = useCallback(() => {
    clearPolling()
    inFlightRef.current = false
    setDesignerId(null)
    setStatus('idle')
    setData(null)
    setMessage(null)
    setError(null)
  }, [clearPolling])

  const runPolling = useCallback(async () => {
    if (!enabled || designerId == null || inFlightRef.current) {
      return
    }

    inFlightRef.current = true

    try {
      const result = await fetcher(designerId)

      setData(result.data ?? null)
      setMessage(result.message ?? null)

      if (result.done) {
        setStatus('success')
        clearPolling()
        return
      }

      setStatus('polling')

      timerRef.current = window.setTimeout(() => {
        void runPolling()
      }, pollIntervalMs)
    } catch (caught) {
      const nextError =
        caught instanceof Error
          ? caught
          : new Error('디자이너 상태 조회에 실패했습니다.')

      setError(nextError)
      setMessage(nextError.message)
      setStatus('error')
      clearPolling()
    } finally {
      inFlightRef.current = false
    }
  }, [clearPolling, designerId, enabled, fetcher, pollIntervalMs])

  const startPolling = useCallback(
    (nextDesignerId: number) => {
      clearPolling()
      inFlightRef.current = false
      setDesignerId(nextDesignerId)
      setStatus('polling')
      setData(null)
      setMessage(null)
      setError(null)
    },
    [clearPolling],
  )

  const stopPolling = useCallback(() => {
    clearPolling()
    inFlightRef.current = false
    setStatus((currentStatus) =>
      currentStatus === 'success' ? currentStatus : 'idle',
    )
  }, [clearPolling])

  useEffect(() => {
    if (!enabled || designerId == null || status !== 'polling') {
      return
    }

    void runPolling()

    return () => {
      clearPolling()
    }
  }, [clearPolling, designerId, enabled, runPolling, status])

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
    designerId,
    isIdle: status === 'idle',
    isPolling: status === 'polling',
    isSuccess: status === 'success',
    isError: status === 'error',
    startPolling,
    stopPolling,
    reset,
  }
}
