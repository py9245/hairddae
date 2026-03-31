import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { auth } from './lib/auth'
import { registerPwaServiceWorker } from './lib/pwa'
import { queryClient } from './lib/query-client'
import { router } from './router'

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Root element not found')
}

const publicPaths = new Set([
  '/',
  '/landing',
  '/auth/login',
  '/auth/signup',
  '/auth/google-callback',
])

auth.subscribe(() => {
  if (auth.isAuthenticated()) {
    return
  }

  const { pathname } = router.state.location
  if (publicPaths.has(pathname)) {
    return
  }

  void queryClient.clear()
  void router.navigate({ to: '/' })
})

registerPwaServiceWorker()

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
