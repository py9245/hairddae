const ACCESS_TOKEN_STORAGE_KEY = 'ssafy-access-token'
const USER_ID_STORAGE_KEY = 'ssafy-user-id'

type AuthListener = () => void

const listeners = new Set<AuthListener>()
const BaseUrl = "/api"

function notifyListeners() {
  for (const listener of listeners) {
    listener()
  }
}

function readStorage() {
  if (typeof window === 'undefined') {
    return null
  }

  return window.sessionStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
}

export const auth = {
  isAuthenticated() {
    return Boolean(readStorage())
  },
  getAccessToken() {
    return readStorage()
  },
  getUserId() {
    if (typeof window === 'undefined') {
      return null
    }

    return window.sessionStorage.getItem(USER_ID_STORAGE_KEY)
  },
  login(accessToken: string, userId: string) {
    window.sessionStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken)
    window.sessionStorage.setItem(USER_ID_STORAGE_KEY, userId)
    notifyListeners()
  },
  logout() {
    window.sessionStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
    window.sessionStorage.removeItem(USER_ID_STORAGE_KEY)
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
  const res = await fetch(`${BaseUrl}/accounts/signin/`, {
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
}

export async function loginApi(payload: LoginRequest): Promise<LoginResponse> {
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

export async function logoutApi() {
  const accessToken = auth.getAccessToken()
  if (!accessToken) return

  await fetch(`${BaseUrl}/accounts/logout/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    credentials: 'include',
    body: JSON.stringify({
      allDevices: false,
    }),
  }).catch(() => null)
}
