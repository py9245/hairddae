import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { API_BASE_URL, buildApiUrl } from '@/lib/api'

type HealthResponse = {
  service: string
  status: string
  timestamp: string
}

function Home() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)

  const checkHealth = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(buildApiUrl('/health'))
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = (await response.json()) as HealthResponse
      setHealth(data)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setError(message)
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void checkHealth()
  }, [checkHealth])

  return (
    <div className="app-frame-shell">
      <div className="app-frame">
        <main className="flex min-h-dvh flex-col items-start justify-center gap-4 p-6">
          <h1 className="text-2xl font-semibold">FE ↔ BE Health Check</h1>
          <p className="text-sm text-muted-foreground">
            API Base: {API_BASE_URL}
          </p>

          <Button onClick={() => void checkHealth()} disabled={loading}>
            {loading ? 'Checking...' : 'Check /api/health'}
          </Button>

          {error && <p className="text-sm text-red-600">Failed: {error}</p>}

          {health && (
            <pre className="w-full overflow-auto rounded-md border p-3 text-sm">
              {JSON.stringify(health, null, 2)}
            </pre>
          )}
        </main>
      </div>
    </div>
  )
}

export default Home
