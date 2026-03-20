const AUTH_STORAGE_KEY = 'ssafy-authenticated'
const ACCESS_TOKEN_STORAGE_KEY = 'ssafy-access-token'

type AuthListener = () => void

const listeners = new Set<AuthListener>()
const BaseUrl = '/api'
const shouldSimulateSignup = import.meta.env.VITE_SIMULATE_SIGNUP === 'true'
const shouldSimulateLogin = import.meta.env.VITE_SIMULATE_LOGIN === 'true'

function notifyListeners() {
  for (const listener of listeners) {
    listener()
  }
}

function readStorage() {
  if (typeof window === 'undefined') {
    return false
  }

  return window.localStorage.getItem(AUTH_STORAGE_KEY) === 'true'
}

export function getStoredAccessToken() {
  if (typeof window === 'undefined') {
    return null
  }

  return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
}

export const auth = {
  isAuthenticated() {
    return readStorage()
  },
  login(accessToken?: string | null) {
    window.localStorage.setItem(AUTH_STORAGE_KEY, 'true')
    if (accessToken) {
      window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken)
    }
    notifyListeners()
  },
  logout() {
    window.localStorage.removeItem(AUTH_STORAGE_KEY)
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
    notifyListeners()
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
  accessToken: string
  refreshToken: string
}

export async function loginApi(payload: LoginRequest): Promise<LoginResponse> {
  if (shouldSimulateLogin) {
    await new Promise((resolve) => window.setTimeout(resolve, 500))

    return {
      code: 200,
      message: '로그인에 성공했습니다.',
      userID: payload.userID,
      accessToken: 'mock-access-token',
      refreshToken: 'mock-refresh-token',
    }
  }

  const res = await fetch(`${BaseUrl}/accounts/login/`, {
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
