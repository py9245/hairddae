import { Download, RefreshCw, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { applyPwaUpdate, PWA_UPDATE_READY_EVENT } from '@/lib/pwa'

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{
    outcome: 'accepted' | 'dismissed'
    platform: string
  }>
}

const INSTALL_DISMISS_KEY = 'pwa-install-dismissed'
const IOS_HINT_DISMISS_KEY = 'pwa-ios-hint-dismissed'

function isStandaloneMode() {
  if (typeof window === 'undefined') {
    return false
  }

  const navigatorWithStandalone = navigator as Navigator & {
    standalone?: boolean
  }

  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    Boolean(navigatorWithStandalone.standalone)
  )
}

function isIosSafari() {
  if (typeof window === 'undefined') {
    return false
  }

  const userAgent = window.navigator.userAgent.toLowerCase()
  const isIos = /iphone|ipad|ipod/.test(userAgent)
  const isSafari =
    /safari/.test(userAgent) && !/crios|fxios|edgios/.test(userAgent)

  return isIos && isSafari
}

export function PwaBanner() {
  const [installPrompt, setInstallPrompt] =
    useState<BeforeInstallPromptEvent | null>(null)
  const [updateReady, setUpdateReady] = useState(false)
  const [isInstalled, setIsInstalled] = useState(() => isStandaloneMode())
  const [installDismissed, setInstallDismissed] = useState(() => {
    if (typeof window === 'undefined') {
      return false
    }

    return window.localStorage.getItem(INSTALL_DISMISS_KEY) === '1'
  })
  const [iosHintDismissed, setIosHintDismissed] = useState(() => {
    if (typeof window === 'undefined') {
      return false
    }

    return window.localStorage.getItem(IOS_HINT_DISMISS_KEY) === '1'
  })

  useEffect(() => {
    const handleBeforeInstallPrompt = (event: Event) => {
      event.preventDefault()
      setInstallPrompt(event as BeforeInstallPromptEvent)
      setInstallDismissed(false)
    }

    const handleAppInstalled = () => {
      setInstallPrompt(null)
      setIsInstalled(true)
      setInstallDismissed(true)
      window.localStorage.setItem(INSTALL_DISMISS_KEY, '1')
    }

    const handleUpdateReady = () => {
      setUpdateReady(true)
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleAppInstalled)
    window.addEventListener(PWA_UPDATE_READY_EVENT, handleUpdateReady)

    return () => {
      window.removeEventListener(
        'beforeinstallprompt',
        handleBeforeInstallPrompt,
      )
      window.removeEventListener('appinstalled', handleAppInstalled)
      window.removeEventListener(PWA_UPDATE_READY_EVENT, handleUpdateReady)
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
      return
    }

    let didReload = false

    const handleControllerChange = () => {
      if (didReload) {
        return
      }

      didReload = true
      window.location.reload()
    }

    navigator.serviceWorker.addEventListener(
      'controllerchange',
      handleControllerChange,
    )

    return () => {
      navigator.serviceWorker.removeEventListener(
        'controllerchange',
        handleControllerChange,
      )
    }
  }, [])

  const showInstallBanner =
    !isInstalled && !installDismissed && installPrompt !== null
  const showIosHint =
    !isInstalled && !iosHintDismissed && !installPrompt && isIosSafari()

  if (!updateReady && !showInstallBanner && !showIosHint) {
    return null
  }

  return (
    <aside className="pointer-events-none absolute inset-x-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-50">
      <div className="pointer-events-auto rounded-[28px] border border-white/70 bg-white/92 p-4 shadow-[0_20px_60px_rgba(79,64,64,0.18)] backdrop-blur">
        {updateReady ? (
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-primary-100 text-primary-300">
              <RefreshCw className="size-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-text-warm-500">
                새 버전을 사용할 수 있어요
              </p>
              <p className="text-xs text-text-warm-200">
                지금 새로고침하면 최신 PWA 자산으로 교체됩니다.
              </p>
            </div>
            <Button
              type="button"
              variant="splash"
              size="sm"
              className="rounded-full px-4"
              onClick={() => {
                void applyPwaUpdate()
              }}
            >
              업데이트
            </Button>
          </div>
        ) : showInstallBanner ? (
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-primary-100 text-primary-300">
              <Download className="size-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-text-warm-500">
                헤어때를 앱처럼 설치할 수 있어요
              </p>
              <p className="text-xs text-text-warm-200">
                홈 화면에 추가하면 전체 화면으로 더 빠르게 실행됩니다.
              </p>
            </div>
            <Button
              type="button"
              variant="splash"
              size="sm"
              className="rounded-full px-4"
              onClick={() => {
                if (!installPrompt) {
                  return
                }

                void (async () => {
                  await installPrompt.prompt()
                  const choice = await installPrompt.userChoice
                  if (choice.outcome !== 'accepted') {
                    setInstallDismissed(true)
                    window.localStorage.setItem(INSTALL_DISMISS_KEY, '1')
                  }
                  setInstallPrompt(null)
                })()
              }}
            >
              설치
            </Button>
            <button
              type="button"
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-text-warm-200 transition hover:bg-neutral-100 hover:text-text-warm-500"
              onClick={() => {
                setInstallDismissed(true)
                window.localStorage.setItem(INSTALL_DISMISS_KEY, '1')
              }}
              aria-label="설치 배너 닫기"
            >
              <X className="size-4" />
            </button>
          </div>
        ) : (
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-primary-100 text-primary-300">
              <Download className="size-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-text-warm-500">
                iPhone에서는 직접 홈 화면에 추가해 주세요
              </p>
              <p className="text-xs leading-5 text-text-warm-200">
                Safari 공유 메뉴에서{' '}
                <span className="font-medium">홈 화면에 추가</span>를 선택하면
                설치형 PWA로 사용할 수 있습니다.
              </p>
            </div>
            <button
              type="button"
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-text-warm-200 transition hover:bg-neutral-100 hover:text-text-warm-500"
              onClick={() => {
                setIosHintDismissed(true)
                window.localStorage.setItem(IOS_HINT_DISMISS_KEY, '1')
              }}
              aria-label="iOS 설치 안내 닫기"
            >
              <X className="size-4" />
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}
