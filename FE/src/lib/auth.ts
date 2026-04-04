import { queryClient } from './query-client'

type AuthListener = () => void

type CookieStoreCookie = {
  name: string
}

type CookieStoreLike = {
  getAll(): Promise<CookieStoreCookie[]>
  delete(name: string): Promise<void>
}

const listeners = new Set<AuthListener>()
const BaseUrl = '/api'
const shouldSimulateSignup = import.meta.env.VITE_SIMULATE_SIGNUP === 'true'
const shouldSimulateLogin = import.meta.env.VITE_SIMULATE_LOGIN === 'true'

export const ME_QUERY_KEY = ['me'] as const
export const ME_QUERY_STALE_TIME = 5 * 60 * 1000

type AuthStatus = 'unknown' | 'authenticated' | 'anonymous'

let authStatus: AuthStatus = 'unknown'
let authCheckPromise: Promise<boolean> | null = null
let refreshPromise: Promise<boolean> | null = null
let suppressRefreshUntil = 0

function notifyListeners() {
  for (const listener of listeners) {
    listener()
  }
}

async function clearClientCookies() {
  if (typeof window === 'undefined') {
    return
  }

  const cookieStore = (window as { cookieStore?: CookieStoreLike }).cookieStore
  if (!cookieStore) {
    return
  }

  const cookies = await cookieStore.getAll()

  for (const cookie of cookies) {
    try {
      await cookieStore.delete(cookie.name)
    } catch {}
  }
}

async function clearSession() {
  await clearClientCookies()
  await queryClient.cancelQueries({ queryKey: ME_QUERY_KEY })
  queryClient.removeQueries({ queryKey: ME_QUERY_KEY })
  setAuthStatus('anonymous')
}

function setAuthStatus(nextStatus: AuthStatus) {
  if (authStatus === nextStatus) {
    return
  }

  authStatus = nextStatus
  notifyListeners()
}

async function readErrorMessage(
  response: Response,
  fallbackMessage: string,
): Promise<string> {
  const data = await response.json().catch(() => null)
  return data?.message ?? fallbackMessage
}

export type MeResponse = {
  code: number
  message: string
  userID: string
  grade?: number | null
  birthDate: string | null
  gender: string | null
}

export async function fetchMe(): Promise<MeResponse | null> {
  const response = await fetch(`${BaseUrl}/mypage/user/`, {
    credentials: 'include',
  })

  if (response.status === 401) {
    return null
  }

  if (!response.ok) {
    throw new Error(
      await readErrorMessage(response, '인증 상태를 확인하지 못했습니다.'),
    )
  }

  return response.json()
}

export async function getCachedMe(): Promise<MeResponse | null> {
  return queryClient.fetchQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: fetchMe,
    staleTime: ME_QUERY_STALE_TIME,
  })
}

async function refreshSession(): Promise<boolean> {
  if (refreshPromise) {
    return refreshPromise
  }

  refreshPromise = (async () => {
    const response = await fetch(`${BaseUrl}/accounts/refreshToken/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({ rotate: false }),
    })

    if (response.status === 401) {
      suppressRefreshUntil = Date.now() + 250
      return false
    }

    if (!response.ok) {
      throw new Error(
        await readErrorMessage(response, '세션을 갱신하지 못했습니다.'),
      )
    }

    return true
  })().finally(() => {
    refreshPromise = null
  })

  return refreshPromise
}

async function resolveAuthStatus() {
  const me = await fetchMe()
  if (me) {
    setAuthStatus('authenticated')
    return true
  }

  if (Date.now() < suppressRefreshUntil) {
    await clearSession()
    return false
  }

  const refreshed = await refreshSession()
  if (!refreshed) {
    await clearSession()
    return false
  }

  const refreshedMe = await fetchMe()
  const isAuthenticated = refreshedMe != null
  setAuthStatus(isAuthenticated ? 'authenticated' : 'anonymous')
  return isAuthenticated
}

export const auth = {
  isAuthenticated() {
    return authStatus === 'authenticated'
  },
  async ensureAuthenticated() {
    if (authStatus === 'authenticated') {
      return true
    }

    if (authCheckPromise) {
      return authCheckPromise
    }

    authCheckPromise = resolveAuthStatus().finally(() => {
      authCheckPromise = null
    })

    return authCheckPromise
  },
  login() {
    void queryClient.invalidateQueries({ queryKey: ME_QUERY_KEY })
    setAuthStatus('authenticated')
  },
  async expireSession() {
    await clearSession()
  },
  async logout() {
    try {
      await fetch(`${BaseUrl}/accounts/logout`, {
        method: 'POST',
        credentials: 'include',
      })
    } catch (error) {
      console.error('Failed to call logout API.', error)
    } finally {
      await clearSession()
    }
  },
  subscribe(listener: AuthListener) {
    listeners.add(listener)

    return () => {
      listeners.delete(listener)
    }
  },
}

export type AuthStore = typeof auth

export type SignUpRequest = {
  userID: string
  password: string
  passwordCheck: string
  birthDate?: string
  gender?: 'M' | 'F'
}

export type SignUpResponse = {
  message: string
  userID: string
}

export async function signUpApi(
  payload: SignUpRequest,
): Promise<SignUpResponse> {
  if (shouldSimulateSignup) {
    await new Promise((resolve) => window.setTimeout(resolve, 500))

    return {
      message: '회원가입이 완료되었습니다.',
      userID: payload.userID,
    }
  }

  const res = await fetch(`${BaseUrl}/accounts/signup/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    throw new Error(errorBody?.message ?? '회원가입에 실패했습니다.')
  }

  return res.json()
}

export type LoginRequest = {
  userID: string
  password: string
}

export type LoginResponse = {
  code: number
  message: string
  userID: string
}

export async function loginApi(payload: LoginRequest): Promise<LoginResponse> {
  if (shouldSimulateLogin) {
    await new Promise((resolve) => window.setTimeout(resolve, 500))

    return {
      code: 200,
      message: '로그인에 성공했습니다.',
      userID: payload.userID,
    }
  }

  const res = await fetch(`${BaseUrl}/accounts/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(payload),
  })

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    throw new Error(data?.message ?? '로그인에 실패했습니다.')
  }

  return data
}
