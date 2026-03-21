import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Outlet,
  redirect,
} from '@tanstack/react-router'
import type { ReactElement } from 'react'
import { z } from 'zod'
import Adsense from '@/app/adsense'
import Camera from '@/app/camera'
import HairList from '@/app/hairlist'
import Login from '@/app/login'
import Main from '@/app/main'
import MyPage from '@/app/mypage'
import SignUp from '@/app/sign-up'
import Splash from '@/app/splash'
import { BottomNav } from '@/components/bottom-nav'
import { NotFoundPage } from '@/components/not-found-page'
import { type AuthStore, auth } from '@/lib/auth'

type RouterContext = {
  auth: AuthStore
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
  notFoundComponent: NotFoundPage,
})

const splashRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: Splash,
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
const myPageRoute = createProtectedRoute('mypage', MyPage)
const hairListRoute = createProtectedRoute('hairlist', HairList, (search) =>
  hairListSearchSchema.parse(search),
)

const routeTree = rootRoute.addChildren([
  splashRoute,
  authRoute.addChildren([loginRoute, signupRoute]),
  mainRoute,
  cameraRoute,
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
  return (
    <div className="app-frame-shell flex items-center justify-center gap-10">
      <Adsense />
      <div className="app-frame">
        <div className="app-frame-content">
          <Outlet />
        </div>
        <BottomNav />
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
