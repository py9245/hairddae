import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Outlet,
  redirect,
} from '@tanstack/react-router'
import { type ReactElement } from 'react'
import Camera from '@/app/camera'
import Login from '@/app/login'
import SignUp from '@/app/sign-up'
import Splash from '@/app/splash'
import { BottomNav } from '@/components/bottom-nav'
import { NotFoundPage } from '@/components/not-found-page'
import { PageShell } from '@/components/page-shell'
import { ProfileCard } from '@/components/profile-card'
import { Button } from '@/components/ui/button'
import { type AuthStore, auth } from '@/lib/auth'
import Adsense from '@/app/Adsense'

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

const routeTree = rootRoute.addChildren([
  splashRoute,
  authRoute.addChildren([loginRoute, signupRoute]),
  mainRoute,
  cameraRoute,
  myPageRoute,
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
  path: 'main' | 'camera' | 'mypage',
  component: () => ReactElement,
) {
  return createRoute({
    getParentRoute: () => rootRoute,
    path,
    // beforeLoad: ({ context, location }) => {
    //   if (!context.auth.isAuthenticated()) {
    //     throw redirect({
    //       to: '/auth/login',
    //       search: {
    //         redirect: location.href,
    //       },
    //     })
    //   }
    // },
    component,
  })
}

function RootLayout() {
  return (
    <div className="app-frame-shell flex justify-center gap-10">
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
  async function handleLogout() {
    auth.logout()
    await router.navigate({ to: '/' })
  }

  return (
    <PageShell
      accent="#0ea5e9"
      badge="Main"
      title="메인 페이지"
      description="로그인 후 처음 진입하는 보호 영역입니다. 이후 실서비스 피드, 알림, 추천 동선 등을 연결할 수 있습니다."
      action={
        <Button
          variant="outline"
          className="rounded-full border-white/30 bg-white/10 text-white hover:bg-white/20 hover:text-white"
          onClick={() => void handleLogout()}
        >
          로그아웃
        </Button>
      }
    >
      <div className="grid gap-4 md:grid-cols-3">
        <GlassPanel
          title="Service status"
          body="백엔드 상태 카드나 요약 지표를 배치할 영역"
        />
        <GlassPanel
          title="Recent activity"
          body="최근 촬영 기록, 추천 콘텐츠, 배너 영역"
        />
        <GlassPanel
          title="Quick actions"
          body="Camera / My Page로 이동하는 액션 모듈"
        />
      </div>
    </PageShell>
  )
}

function MyPage() {
  async function handleLogout() {
    auth.logout()
    await router.navigate({ to: '/' })
  }

  const profile = {
    nickname: 'mijin.develop',
    age: null, // null이면 비공개 처리됨
    gender: null,
    avatarVariant: 1 as const,
  }

  return (
    <PageShell
      accent="#8b5cf6"
      badge="My Page"
      title="마이페이지"
      description="프로필, 기록, 환경설정 등을 담는 보호 페이지입니다."
    >
      <div className="grid gap-4">
        <ProfileCard profile={profile} onLogout={() => void handleLogout()} />

        <div className="grid gap-4 md:grid-cols-2">
          <GlassPanel title="History" body="촬영 이력, 즐겨찾기, 최근 활동" />
          <GlassPanel title="Preferences" body="알림, 접근성, 화면 옵션" />
          <GlassPanel title="Security" body="계정 관리, 연결된 인증 수단" />
        </div>
      </div>
    </PageShell>
  )
}

function GlassPanel({ title, body }: { title: string; body: string }) {
  return (
    <section className="rounded-[1.5rem] border border-white/15 bg-black/20 p-5">
      <p className="text-sm font-semibold text-white/80">{title}</p>
      <p className="mt-3 text-sm leading-6 text-white/65">{body}</p>
    </section>
  )
}
