import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Outlet,
  redirect,
  useRouterState,
} from '@tanstack/react-router'
import {
  type ReactElement,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { z } from 'zod'
import Camera from '@/app/camera'
import Chat from '@/app/chat'
import GoogleCallback from '@/app/google-callback'
import HairList from '@/app/hairlist'
import Landing from '@/app/landing'
import Login from '@/app/login'
import Main from '@/app/main'
import MyPage from '@/app/mypage'
import SignUp from '@/app/sign-up'
import Splash from '@/app/splash'
import { BottomNav } from '@/components/bottom-nav'
import { NotFoundPage } from '@/components/not-found-page'
import { ReviewModal } from '@/components/review-modal'
import { type AuthStore, auth, fetchMe } from '@/lib/auth'

type RouterContext = {
  auth: AuthStore
}

type ReviewModalPreference = {
  dismissedUntil?: number
  completed?: boolean
}

const REVIEW_MODAL_STORAGE_KEY = 'review-modal-preferences'
const REVIEW_MODAL_DELAY_MS = 60_000
const REVIEW_MODAL_DEFER_MS = 14 * 24 * 60 * 60 * 1000

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
  notFoundComponent: NotFoundPage,
})

const splashRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: Splash,
})

const landingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'landing',
  component: Landing,
})

const authRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'auth',
  component: AuthLayout,
  notFoundComponent: NotFoundPage,
})

const loginSearchSchema = z.object({
  redirect: z.string().optional(),
})

const loginRoute = createRoute({
  getParentRoute: () => authRoute,
  path: 'login',
  validateSearch: (search) => loginSearchSchema.parse(search),
  beforeLoad: async ({ context }) => {
    if (await context.auth.ensureAuthenticated()) {
      throw redirect({ to: '/main' })
    }
  },
  component: Login,
})

const signupRoute = createRoute({
  getParentRoute: () => authRoute,
  path: 'signup',
  component: SignUp,
})

const googleCallbackSearchSchema = z.object({
  idToken: z.string().optional(),
  state: z.string().optional(),
  error: z.string().optional(),
  refresh: z.string().optional(),
  userid: z.string().optional(),
  isonboarding: z.string().optional(),
  is_superuser: z.string().optional(),
})

const googleCallbackRoute = createRoute({
  getParentRoute: () => authRoute,
  path: 'google-callback',
  validateSearch: (search) => googleCallbackSearchSchema.parse(search),
  component: GoogleCallback,
})

const hairListSearchSchema = z.object({
  category: z.string().catch('').optional(),
})

const cameraSearchSchema = z.object({
  applyLatest: z.coerce.boolean().optional(),
  hairId: z.coerce.number().int().positive().optional(),
})

const mainRoute = createProtectedRoute('main', MainPage)
const cameraRoute = createProtectedRoute('camera', Camera, (search) =>
  cameraSearchSchema.parse(search),
)
const chatRoute = createProtectedRoute('chat', Chat)
const myPageRoute = createProtectedRoute('mypage', MyPage)
const hairListRoute = createProtectedRoute('hairlist', HairList, (search) =>
  hairListSearchSchema.parse(search),
)

const routeTree = rootRoute.addChildren([
  splashRoute,
  landingRoute,
  authRoute.addChildren([loginRoute, signupRoute, googleCallbackRoute]),
  mainRoute,
  cameraRoute,
  chatRoute,
  myPageRoute,
  hairListRoute,
])

export const router = createRouter({
  routeTree,
  context: {
    auth,
  },
  defaultPreload: 'intent',
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

function createProtectedRoute<
  TPath extends string,
  TSearchSchema extends Record<string, unknown> = Record<string, never>,
>(
  path: TPath,
  component: () => ReactElement,
  validateSearch?: (search: Record<string, unknown>) => TSearchSchema,
) {
  return createRoute({
    getParentRoute: () => rootRoute,
    path,
    validateSearch,
    beforeLoad: async ({ context, location }) => {
      if (!(await context.auth.ensureAuthenticated())) {
        throw redirect({
          to: '/auth/login',
          search: {
            redirect: location.href,
          },
        })
      }
    },
    component,
  })
}

function RootLayout() {
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false)
  const reviewTimerRef = useRef<number | null>(null)
  const reviewTimerUserIdRef = useRef<string | null>(null)
  const startedReviewTimerUserIdRef = useRef<string | null>(null)
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })

  const readReviewModalPreferences = useCallback(() => {
    try {
      const raw = window.localStorage.getItem(REVIEW_MODAL_STORAGE_KEY)
      if (!raw) {
        return {}
      }

      return JSON.parse(raw) as Record<string, ReviewModalPreference>
    } catch {
      return {}
    }
  }, [])

  const writeReviewModalPreference = useCallback(
    (userId: string, nextPreference: ReviewModalPreference) => {
      const preferences = readReviewModalPreferences()
      preferences[userId] = nextPreference
      window.localStorage.setItem(
        REVIEW_MODAL_STORAGE_KEY,
        JSON.stringify(preferences),
      )
    },
    [readReviewModalPreferences],
  )

  const deferReviewModal = useCallback(async () => {
    const me = await fetchMe().catch(() => null)
    if (me) {
      writeReviewModalPreference(me.userID, {
        dismissedUntil: Date.now() + REVIEW_MODAL_DEFER_MS,
      })
    }
    setIsReviewModalOpen(false)
  }, [writeReviewModalPreference])

  const submitReviewModal = useCallback(async () => {
    const me = await fetchMe().catch(() => null)
    if (me) {
      writeReviewModalPreference(me.userID, {
        completed: true,
      })
    }
    setIsReviewModalOpen(false)
  }, [writeReviewModalPreference])

  const resetReviewModalTimer = useCallback(() => {
    if (reviewTimerRef.current != null) {
      window.clearTimeout(reviewTimerRef.current)
      reviewTimerRef.current = null
    }

    reviewTimerUserIdRef.current = null
    startedReviewTimerUserIdRef.current = null
    setIsReviewModalOpen(false)
  }, [])

  useEffect(() => {
    if (pathname !== '/main') {
      return
    }

    void (async () => {
      const me = await fetchMe().catch(() => null)
      if (!me) {
        return
      }

      if (startedReviewTimerUserIdRef.current === me.userID) {
        return
      }

      if (reviewTimerRef.current != null) {
        window.clearTimeout(reviewTimerRef.current)
      }

      startedReviewTimerUserIdRef.current = me.userID
      reviewTimerUserIdRef.current = me.userID
      reviewTimerRef.current = window.setTimeout(() => {
        void (async () => {
          const currentMe = await fetchMe().catch(() => null)
          if (!currentMe || currentMe.userID !== reviewTimerUserIdRef.current) {
            return
          }

          const preference = readReviewModalPreferences()[currentMe.userID]
          if (preference?.completed) {
            return
          }

          if (
            preference?.dismissedUntil != null &&
            preference.dismissedUntil > Date.now()
          ) {
            return
          }

          setIsReviewModalOpen(true)
        })()
      }, REVIEW_MODAL_DELAY_MS)
    })()
  }, [pathname, readReviewModalPreferences])

  useEffect(() => {
    return auth.subscribe(() => {
      if (!auth.isAuthenticated()) {
        resetReviewModalTimer()
      }
    })
  }, [resetReviewModalTimer])

  useEffect(() => {
    return () => {
      resetReviewModalTimer()
    }
  }, [resetReviewModalTimer])

  return (
    <div className="app-frame-shell flex items-center justify-center gap-10">
      <div className="app-frame">
        <div className="app-frame-content">
          <Outlet />
        </div>
        <BottomNav />
        {isReviewModalOpen ? (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
            <ReviewModal
              open={isReviewModalOpen}
              onClose={() => {
                void deferReviewModal()
              }}
              onDefer={() => {
                void deferReviewModal()
              }}
              onSubmit={() => {
                void submitReviewModal()
              }}
            />
          </div>
        ) : null}
      </div>
    </div>
  )
}

function AuthLayout() {
  return <Outlet />
}

function MainPage() {
  return <Main />
}
