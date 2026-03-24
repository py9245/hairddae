const SERVICE_WORKER_URL = '/sw.js'

export const PWA_UPDATE_READY_EVENT = 'pwa:update-ready'

let hasRegisteredServiceWorker = false
let currentRegistration: ServiceWorkerRegistration | null = null

function notifyUpdateReady() {
  window.dispatchEvent(new Event(PWA_UPDATE_READY_EVENT))
}

export function registerPwaServiceWorker() {
  if (
    hasRegisteredServiceWorker ||
    typeof window === 'undefined' ||
    !('serviceWorker' in navigator)
  ) {
    return
  }

  hasRegisteredServiceWorker = true

  window.addEventListener(
    'load',
    () => {
      void (async () => {
        try {
          const registration =
            await navigator.serviceWorker.register(SERVICE_WORKER_URL)
          currentRegistration = registration

          if (registration.waiting) {
            notifyUpdateReady()
          }

          registration.addEventListener('updatefound', () => {
            const installingWorker = registration.installing
            if (!installingWorker) {
              return
            }

            installingWorker.addEventListener('statechange', () => {
              if (
                installingWorker.state === 'installed' &&
                navigator.serviceWorker.controller
              ) {
                notifyUpdateReady()
              }
            })
          })
        } catch (error) {
          console.error('PWA service worker registration failed', error)
        }
      })()
    },
    { once: true },
  )
}

export async function applyPwaUpdate() {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
    return false
  }

  const registration =
    currentRegistration ??
    (await navigator.serviceWorker.getRegistration(SERVICE_WORKER_URL)) ??
    (await navigator.serviceWorker.getRegistration())

  if (!registration?.waiting) {
    return false
  }

  registration.waiting.postMessage({ type: 'SKIP_WAITING' })
  return true
}
