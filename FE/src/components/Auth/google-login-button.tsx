import { useNavigate } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'
import { GoogleButton } from '@/components/google-button'

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: {
          initialize: (options: {
            client_id: string
            callback: (response: { credential?: string }) => void
            ux_mode?: 'popup' | 'redirect'
          }) => void
          renderButton: (
            parent: HTMLElement,
            options: {
              type?: 'standard' | 'icon'
              theme?: 'outline' | 'filled_blue' | 'filled_black'
              size?: 'large' | 'medium' | 'small'
              text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin'
              shape?: 'rectangular' | 'pill' | 'circle' | 'square'
              logo_alignment?: 'left' | 'center'
              width?: string | number
            },
          ) => void
          prompt: () => void
        }
      }
    }
  }
}

const GOOGLE_IDENTITY_SCRIPT_SRC = 'https://accounts.google.com/gsi/client'

function loadGoogleIdentityScript(): Promise<void> {
  if (typeof window === 'undefined') {
    return Promise.resolve()
  }

  if (window.google?.accounts?.id) {
    return Promise.resolve()
  }

  const existing = document.querySelector<HTMLScriptElement>(
    `script[src="${GOOGLE_IDENTITY_SCRIPT_SRC}"]`,
  )

  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener(
        'error',
        () => reject(new Error('Google 스크립트를 불러오지 못했습니다.')),
        { once: true },
      )
    })
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = GOOGLE_IDENTITY_SCRIPT_SRC
    script.async = true
    script.defer = true
    script.onload = () => resolve()
    script.onerror = () =>
      reject(new Error('Google 스크립트를 불러오지 못했습니다.'))
    document.head.appendChild(script)
  })
}

export function GoogleLoginButton() {
  const navigate = useNavigate()
  const buttonContainerRef = useRef<HTMLDivElement | null>(null)
  const buttonScaleRef = useRef<HTMLDivElement | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

    if (!clientId?.trim()) {
      setError('Google Client ID가 설정되지 않았습니다.')
      return
    }

    const renderGoogleButton = async () => {
      try {
        await loadGoogleIdentityScript()

        if (
          cancelled ||
          !buttonContainerRef.current ||
          !buttonScaleRef.current ||
          !window.google?.accounts?.id
        ) {
          return
        }

        buttonContainerRef.current.innerHTML = ''
        const targetWidth = buttonScaleRef.current.clientWidth
        const scale = 56 / 40
        const renderedWidth = Math.max(240, Math.floor(targetWidth / scale))

        window.google.accounts.id.initialize({
          client_id: clientId.trim(),
          callback: ({ credential }) => {
            if (!credential) {
              setError('Google ID 토큰을 받지 못했습니다.')
              return
            }

            void navigate({
              to: '/auth/google-callback',
              search: {
                idToken: credential,
              },
            })
          },
        })

        window.google.accounts.id.renderButton(buttonContainerRef.current, {
          theme: 'outline',
          size: 'large',
          text: 'signin_with',
          shape: 'rectangular',
          logo_alignment: 'left',
          width: renderedWidth,
        })
      } catch (nextError) {
        console.error(nextError)
        setError(
          nextError instanceof Error
            ? nextError.message
            : 'Google 로그인 버튼을 초기화하지 못했습니다.',
        )
      }
    }

    void renderGoogleButton()

    return () => {
      cancelled = true
    }
  }, [navigate])

  return (
    <div className="space-y-2">
      <div className="relative h-14 w-full overflow-hidden">
        <div className="absolute inset-0">
          <GoogleButton
            disabled
            aria-hidden="true"
            tabIndex={-1}
            className="pointer-events-none h-full max-w-none opacity-0"
            label="Google로 로그인"
          />
        </div>
        <div
          ref={buttonScaleRef}
          className="absolute inset-0 flex items-center justify-center overflow-hidden"
        >
          <div
            ref={buttonContainerRef}
            className="origin-center"
            style={{ transform: 'scale(1.4)' }}
          />
        </div>
      </div>
      {error ? (
        <p className="text-center text-sm text-red-500">{error}</p>
      ) : null}
    </div>
  )
}
