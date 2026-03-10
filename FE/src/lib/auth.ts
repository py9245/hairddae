const AUTH_STORAGE_KEY = 'ssafy-authenticated'

type AuthListener = () => void

const listeners = new Set<AuthListener>()

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

export const auth = {
  isAuthenticated() {
    return readStorage()
  },
  login() {
    window.localStorage.setItem(AUTH_STORAGE_KEY, 'true')
    notifyListeners()
  },
  logout() {
    window.localStorage.removeItem(AUTH_STORAGE_KEY)
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
