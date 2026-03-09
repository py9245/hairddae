const DEFAULT_API_BASE_URL = '/api'

function normalizeBaseUrl(rawBaseUrl?: string): string {
  if (!rawBaseUrl) return DEFAULT_API_BASE_URL

  const trimmed = rawBaseUrl.trim()
  if (!trimmed) return DEFAULT_API_BASE_URL

  return trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed
}

export const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL)

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${normalizedPath}`
}
