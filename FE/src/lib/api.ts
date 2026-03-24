import { auth } from '@/lib/auth'

const DEFAULT_API_BASE_URL = '/api'

export type RefreshTokenRequest = {
  rotate: boolean
}

export type RefreshTokenResponse = {
  code: number
  message: string
}

function normalizeBaseUrl(rawBaseUrl?: string): string {
  if (!rawBaseUrl) return DEFAULT_API_BASE_URL

  const trimmed = rawBaseUrl.trim()
  if (!trimmed) return DEFAULT_API_BASE_URL

  return trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed
}

export const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL)

type ApiFetchInit = RequestInit & {
  skipAuthRefresh?: boolean
}

let refreshInFlight: Promise<void> | null = null

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${normalizedPath}`
}

function isRefreshRequest(url: string): boolean {
  return url === buildApiUrl('/accounts/refreshToken/')
}

async function ensureRefreshed(): Promise<void> {
  if (!refreshInFlight) {
    refreshInFlight = refreshAuth({ rotate: false })
      .then(() => undefined)
      .catch(async (error) => {
        await auth.expireSession()
        throw error
      })
      .finally(() => {
        refreshInFlight = null
      })
  }

  return refreshInFlight
}

export async function apiFetch(
  input: string,
  init: ApiFetchInit = {},
): Promise<Response> {
  const { skipAuthRefresh = false, credentials, ...requestInit } = init
  const requestUrl = input.startsWith('http') ? input : buildApiUrl(input)
  const requestCredentials = credentials ?? 'include'

  const response = await fetch(requestUrl, {
    ...requestInit,
    credentials: requestCredentials,
  })

  if (
    response.status !== 401 ||
    skipAuthRefresh ||
    isRefreshRequest(requestUrl)
  ) {
    return response
  }

  await ensureRefreshed()

  return fetch(requestUrl, {
    ...requestInit,
    credentials: requestCredentials,
  })
}

export async function refreshAuth(
  payload: RefreshTokenRequest = { rotate: true },
): Promise<RefreshTokenResponse> {
  const response = await fetch(buildApiUrl('/accounts/refreshToken/'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(payload),
  })

  const data = (await response.json().catch(() => null)) as
    | RefreshTokenResponse
    | { message?: string }
    | null

  if (!response.ok) {
    throw new Error(data?.message ?? '토큰 재인증에 실패했습니다.')
  }

  const code =
    data && 'code' in data && typeof data.code === 'number' ? data.code : 200

  return {
    code,
    message: data?.message ?? '토큰 재인증에 성공했습니다.',
  }
}
