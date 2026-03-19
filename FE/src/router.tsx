import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Outlet,
  redirect,
} from '@tanstack/react-router'
import type { ReactElement } from 'react'
import Adsense from '@/app/adsense'
import Camera from '@/app/camera'
import Login from '@/app/login'
import Main from '@/app/main'
import SignUp from '@/app/sign-up'
import Splash from '@/app/splash'
import { BottomNav } from '@/components/bottom-nav'
import { Header } from '@/components/header'
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

const loginRoute = createRoute({
  getParentRoute: () => authRoute,
  path: 'login',
  beforeLoad: ({ context }) => {
    if (context.auth.isAuthenticated()) {
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

const mainRoute = createProtectedRoute('main', MainPage)
const cameraRoute = createProtectedRoute('camera', Camera)
const myPageRoute = createProtectedRoute('mypage', MyPage)
const hairListRoute = createProtectedRoute('hairlist', HairListPage)

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

function createProtectedRoute(
  path: 'main' | 'camera' | 'mypage' | 'hairlist',
  component: () => ReactElement,
) {
  return createRoute({
    getParentRoute: () => rootRoute,
    path,
    beforeLoad: ({ context, location }) => {
      if (!context.auth.isAuthenticated()) {
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

function MyPage() {
  return (
    <div className="app-frame-page bg-bg-primary">
      <Header label="내정보" />
    </div>
  )
}

function HairListPage() {
  return (
    <div className="app-frame-page bg-bg-primary">
      <Header label="단발컷" />
    </div>
  )
}
