import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Link,
  Outlet,
  redirect,
} from '@tanstack/react-router'
import type { ReactElement } from 'react'
import Camera from '@/app/Camera'
import Login from '@/app/Login'
import SignUp from '@/app/SignUp'
import { BottomNav } from '@/components/bottom-nav'
import { PageShell } from '@/components/page-shell'
import { RouteCard } from '@/components/route-card'
import { Button } from '@/components/ui/button'
import { type AuthStore, auth } from '@/lib/auth'

type RouterContext = {
  auth: AuthStore
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: RootLayout,
})

const splashRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: SplashPage,
})

const authRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'auth',
  component: AuthLayout,
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
  defaultNotFoundComponent: () => (
    <main className="app-frame-page flex items-center justify-center bg-slate-950 px-6 text-white">
      <div className="w-full max-w-md rounded-[1.75rem] border border-white/15 bg-white/10 p-8 text-center backdrop-blur">
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-sky-300">
          404
        </p>
        <h1 className="mt-4 text-3xl font-semibold">Page not found</h1>
        <p className="mt-3 text-sm text-white/70">
          The route does not exist or is no longer available.
        </p>
      </div>
    </main>
  ),
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
    <div className="app-frame-shell">
      <div className="app-frame">
        <main className="app-frame-content">
          <Outlet />
        </main>
        <BottomNav />
      </div>
    </div>
  )
}

function SplashPage() {
  return (
    <main className="app-frame-page bg-[linear-gradient(145deg,#e0f2fe_0%,#f8fafc_35%,#fef3c7_100%)] px-6 py-10 text-slate-950">
      <div className="app-frame-fill mx-auto grid max-w-6xl items-center gap-8 lg:grid-cols-[1.15fr_0.85fr]">
        <RouteCard
          eyebrow="Splash"
          title="Capture starts here."
          description="루트 스플래시는 서비스 진입 허브입니다. 인증 흐름으로 이동하거나, 로그인된 사용자는 핵심 기능으로 바로 들어갈 수 있습니다."
        >
          <div className="flex flex-wrap gap-3">
            <Button asChild className="rounded-full">
              <Link to="/auth/login">로그인으로 이동</Link>
            </Button>
            <Button
              asChild
              variant="outline"
              className="rounded-full bg-transparent"
            >
              <Link to="/auth/signup">회원가입</Link>
            </Button>
          </div>
        </RouteCard>

        <section className="grid gap-4">
          <RoutePreview
            title="Main"
            body="서비스 피드, 상태, 추천 동선"
            className="bg-white/70 text-slate-950"
          />
          <RoutePreview
            title="Camera"
            body="핵심 촬영 경험이 들어갈 보호 페이지"
            className="bg-slate-950 text-white"
          />
          <RoutePreview
            title="My Page"
            body="계정, 기록, 개인화 설정"
            className="bg-amber-100 text-slate-950"
          />
        </section>
      </div>
    </main>
  )
}

function AuthLayout() {
  return (
    <main className="app-frame-page bg-[linear-gradient(180deg,#082f49_0%,#0f172a_50%,#020617_100%)] px-6 py-10 text-white">
      <div className="app-frame-fill mx-auto flex max-w-6xl items-center justify-center">
        <div className="grid w-full items-stretch gap-6 lg:grid-cols-[0.95fr_1.05fr]">
          <section className="hidden rounded-[2rem] border border-white/10 bg-white/5 p-8 backdrop-blur lg:flex lg:flex-col lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-sky-300">
                Auth
              </p>
              <h1 className="mt-4 text-4xl font-semibold tracking-tight">
                계정 진입 흐름
              </h1>
              <p className="mt-4 text-sm leading-6 text-white/70">
                로그인과 회원가입은 `/auth/*` 하위에서 관리합니다. 실제 API 연동
                전까지는 임시 로컬 인증 상태를 사용합니다.
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-white/10 bg-black/20 p-5">
              <p className="text-sm text-white/80">Public routes</p>
              <p className="mt-2 text-xs uppercase tracking-[0.3em] text-white/45">
                / · /auth/login · /auth/signup
              </p>
            </div>
          </section>
          <Outlet />
        </div>
      </div>
    </main>
  )
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
  return (
    <PageShell
      accent="#8b5cf6"
      badge="My Page"
      title="마이페이지"
      description="프로필, 기록, 환경설정 등을 담는 보호 페이지입니다. 현재는 정보 카드와 인증 제어 동선만 구성합니다."
      action={
        <Button
          variant="outline"
          className="rounded-full border-white/30 bg-white/10 text-white hover:bg-white/20 hover:text-white"
          onClick={() => void router.navigate({ to: '/camera' })}
        >
          카메라로
        </Button>
      }
    >
      <div className="grid gap-4 md:grid-cols-2">
        <GlassPanel title="Profile" body="닉네임, 이메일, 아바타, 기본 설정" />
        <GlassPanel title="History" body="촬영 이력, 즐겨찾기, 최근 활동" />
        <GlassPanel title="Preferences" body="알림, 접근성, 화면 옵션" />
        <GlassPanel
          title="Security"
          body="로그아웃, 계정 관리, 연결된 인증 수단"
        />
      </div>
    </PageShell>
  )
}

function RoutePreview({
  title,
  body,
  className,
}: {
  title: string
  body: string
  className: string
}) {
  return (
    <div
      className={`rounded-[1.75rem] border border-slate-200 p-6 shadow-sm ${className}`}
    >
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-2 text-lg font-medium">{body}</p>
    </div>
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
