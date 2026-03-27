import { useNavigate } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

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

type GoogleLoginButtonProps = {
  clientId?: string
  label?: string
  className?: string
  labelClassName?: string
}

function GoogleIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18" className="h-5 w-5 shrink-0">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.56 2.68-3.86 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.33-1.58-5.04-3.7H.96v2.32A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.96 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.28-1.72V4.96H.96A9 9 0 0 0 0 9c0 1.45.35 2.82.96 4.04l3-2.32Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.46 3.44 1.36l2.58-2.58C13.46.9 11.43 0 9 0A9 9 0 0 0 .96 4.96l3 2.32c.7-2.12 2.7-3.7 5.04-3.7Z"
      />
    </svg>
  )
}

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
        () => reject(new Error('Failed to load Google Identity Services.')),
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
      reject(new Error('Failed to load Google Identity Services.'))
    document.head.appendChild(script)
  })
}

export function GoogleLoginButton({
  clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined,
  label = 'Google로 로그인하기',
  className,
  labelClassName,
}: GoogleLoginButtonProps) {
  const navigate = useNavigate()
  const buttonContainerRef = useRef<HTMLDivElement | null>(null)
  const buttonScaleRef = useRef<HTMLDivElement | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    if (!clientId?.trim()) {
      setError('Google Client ID is not configured.')
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
        setError(null)

        const targetWidth = buttonScaleRef.current.clientWidth
        const scale = 56 / 40
        const renderedWidth = Math.max(240, Math.floor(targetWidth / scale))

        window.google.accounts.id.initialize({
          client_id: clientId.trim(),
          callback: ({ credential }) => {
            if (!credential) {
              setError('Failed to receive Google ID token.')
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
            : 'Failed to initialize Google login button.',
        )
      }
    }

    void renderGoogleButton()

    return () => {
      cancelled = true
    }
  }, [clientId, navigate])

  return (
    <div className="space-y-2">
      <div className={cn('relative h-14 w-full overflow-hidden', className)}>
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 inline-flex items-center justify-between rounded-[8px] border border-[#747775] bg-white px-4 text-[#1f1f1f] shadow-none"
        >
          <span className="flex h-5 w-5 items-center justify-center">
            <GoogleIcon />
          </span>
          <span
            className={cn(
              'grow text-center font-["Roboto",arial,sans-serif] text-sm font-medium tracking-[0.25px]',
              labelClassName,
            )}
          >
            {label}
          </span>
          <span className="h-5 w-5 shrink-0" />
        </div>
        <div
          ref={buttonScaleRef}
          className="absolute inset-0 z-10 flex items-center justify-center overflow-hidden opacity-0"
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
