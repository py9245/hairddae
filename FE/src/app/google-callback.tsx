import { useNavigate, useSearch } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { buildApiUrl } from '@/lib/api'
import { auth, fetchMe } from '@/lib/auth'

const GOOGLE_OAUTH_STATE_STORAGE_KEY = 'google_oauth_state'

type GoogleLoginRequest = {
  idToken: string
}

type GoogleLoginResponse = {
  message?: string
}

function readStoredState(): string | null {
  if (typeof window === 'undefined') {
    return null
  }

  return window.sessionStorage.getItem(GOOGLE_OAUTH_STATE_STORAGE_KEY)
}

function clearStoredState() {
  if (typeof window === 'undefined') {
    return
  }

  window.sessionStorage.removeItem(GOOGLE_OAUTH_STATE_STORAGE_KEY)
}

async function exchangeGoogleLogin(
  payload: GoogleLoginRequest,
): Promise<GoogleLoginResponse | null> {
  const response = await fetch(buildApiUrl('/accounts/google-login/'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(payload),
  })

  const data = (await response.json().catch(() => null)) as
    | GoogleLoginResponse
    | { message?: string }
    | null

  if (!response.ok) {
    throw new Error(data?.message ?? '구글 로그인 처리에 실패했습니다.')
  }

  return data
}

export default function GoogleCallback() {
  const navigate = useNavigate()
  const search = useSearch({ from: '/auth/google-callback' })
  const [message, setMessage] = useState('구글 로그인 처리 중입니다...')

  useEffect(() => {
    let cancelled = false

    const finishWithError = async (errorMessage: string) => {
      if (cancelled) {
        return
      }

      setMessage(errorMessage)
      await navigate({
        to: '/auth/login',
        search: {
          redirect: '/main',
        },
        replace: true,
      })
    }

    const run = async () => {
      try {
        if (search.error) {
          throw new Error(`구글 로그인 오류: ${search.error}`)
        }

        if (search.state) {
          const storedState = readStoredState()
          if (storedState && storedState !== search.state) {
            throw new Error('구글 로그인 상태값이 올바르지 않습니다.')
          }
        }

        clearStoredState()

        if (!search.idToken) {
          throw new Error('Google ID 토큰이 없습니다.')
        }

        await exchangeGoogleLogin({
          idToken: search.idToken,
        })

        const me = await fetchMe()
        if (!me) {
          throw new Error('로그인 세션을 확인하지 못했습니다.')
        }

        auth.login()

        await navigate({
          to: '/main',
          replace: true,
        })
      } catch (error) {
        console.error(error)
        const nextMessage =
          error instanceof Error
            ? error.message
            : '구글 로그인 처리에 실패했습니다.'

        await finishWithError(nextMessage)
      }
    }

    void run()

    return () => {
      cancelled = true
    }
  }, [navigate, search])

  return (
    <main className="app-frame-page flex items-center justify-center bg-bg-primary px-6 py-10">
      <p className="text-center text-sm font-medium text-slate-500">
        {message}
      </p>
    </main>
  )
}
