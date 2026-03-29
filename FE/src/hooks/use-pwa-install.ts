import { useEffect, useState } from 'react'

export type BeforeInstallPromptEvent = Event & {
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

export function usePwaInstall() {
  const [installPrompt, setInstallPrompt] =
    useState<BeforeInstallPromptEvent | null>(null)
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

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleAppInstalled)

    return () => {
      window.removeEventListener(
        'beforeinstallprompt',
        handleBeforeInstallPrompt,
      )
      window.removeEventListener('appinstalled', handleAppInstalled)
    }
  }, [])

  return {
    isInstalled,
    showInstallPrompt:
      !isInstalled && !installDismissed && installPrompt !== null,
    showIosInstallHint:
      !isInstalled && !iosHintDismissed && !installPrompt && isIosSafari(),
    dismissInstallPrompt() {
      setInstallDismissed(true)
      window.localStorage.setItem(INSTALL_DISMISS_KEY, '1')
    },
    dismissIosInstallHint() {
      setIosHintDismissed(true)
      window.localStorage.setItem(IOS_HINT_DISMISS_KEY, '1')
    },
    async promptInstall() {
      if (!installPrompt) {
        return null
      }

      await installPrompt.prompt()
      const choice = await installPrompt.userChoice
      setInstallPrompt(null)
      return choice
    },
  }
}
