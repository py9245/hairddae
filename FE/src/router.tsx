import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Link,
  Outlet,
  redirect,
} from '@tanstack/react-router'
import type { ReactElement } from 'react'

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
  component: LoginPage,
})

const signupRoute = createRoute({
  getParentRoute: () => authRoute,
  path: 'signup',
  component: SignupPage,
})

const mainRoute = createProtectedRoute('main', MainPage)
const cameraRoute = createProtectedRoute('camera', CameraPage)
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
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-white">
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
    <>
      <Outlet />
      <div className="fixed bottom-4 left-1/2 z-10 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 rounded-full border border-slate-900/10 bg-white/80 p-2 shadow-lg backdrop-blur">
        <nav className="grid grid-cols-5 gap-2">
          <NavButton to="/" label="Splash" />
          <NavButton to="/auth/login" label="Login" />
          <NavButton to="/main" label="Main" />
          <NavButton to="/camera" label="Camera" />
          <NavButton to="/mypage" label="My" />
        </nav>
      </div>
    </>
  )
}

function NavButton({ to, label }: { to: string; label: string }) {
  return (
    <Button asChild size="sm" variant="ghost" className="rounded-full">
      <Link to={to}>{label}</Link>
    </Button>
  )
}

function SplashPage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(145deg,#e0f2fe_0%,#f8fafc_35%,#fef3c7_100%)] px-6 py-10 text-slate-950">
      <div className="mx-auto grid min-h-[calc(100vh-5rem)] max-w-6xl items-center gap-8 lg:grid-cols-[1.15fr_0.85fr]">
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
    <main className="min-h-screen bg-[linear-gradient(180deg,#082f49_0%,#0f172a_50%,#020617_100%)] px-6 py-10 text-white">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-6xl items-center justify-center">
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

function LoginPage() {
  const redirectTo = getRedirectTarget()

  async function handleLogin() {
    auth.login()
    await router.navigate({ to: redirectTo })
  }

  return (
    <RouteCard
      eyebrow="Login"
      title="로그인"
      description="보호 페이지 접근 시 이 화면으로 리다이렉트됩니다. 현재는 로컬 스토리지에 임시 인증 상태만 기록합니다."
      className="self-center"
    >
      <div className="space-y-4">
        <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">
          <p className="font-medium text-slate-900">테스트 인증</p>
          <p className="mt-2">
            버튼을 누르면 로그인 상태를 만들고 원래 요청 경로 또는 `/main`으로
            이동합니다.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button className="rounded-full" onClick={() => void handleLogin()}>
            로그인 처리
          </Button>
          <Button asChild variant="outline" className="rounded-full">
            <Link to="/auth/signup">회원가입으로 이동</Link>
          </Button>
        </div>
      </div>
    </RouteCard>
  )
}

function SignupPage() {
  return (
    <RouteCard
      eyebrow="Sign Up"
      title="회원가입"
      description="실제 입력 폼과 서버 연동은 이후 단계에서 붙이고, 지금은 auth 영역과 페이지 흐름을 고정합니다."
      className="self-center"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">
          이메일, 비밀번호, 약관 동의
        </div>
        <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">
          소셜 로그인이나 프로필 초기화 자리
        </div>
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <Button asChild className="rounded-full">
          <Link to="/auth/login">로그인으로 돌아가기</Link>
        </Button>
        <Button asChild variant="outline" className="rounded-full">
          <Link to="/">스플래시</Link>
        </Button>
      </div>
    </RouteCard>
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

function CameraPage() {
  return (
    <PageShell
      accent="#f97316"
      badge="Camera"
      title="카메라 페이지"
      description="핵심 기능이 들어갈 독립 라우트입니다. 실제 비디오 프리뷰와 촬영 플로우는 이 영역에 연결하면 됩니다."
      action={
        <Button
          variant="outline"
          className="rounded-full border-white/30 bg-white/10 text-white hover:bg-white/20 hover:text-white"
          onClick={() => void router.navigate({ to: '/main' })}
        >
          메인으로
        </Button>
      }
    >
      <div className="grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
        <section className="flex min-h-80 items-center justify-center rounded-[1.75rem] border border-dashed border-white/30 bg-black/25 p-6">
          <div className="text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-orange-200">
              Preview
            </p>
            <p className="mt-4 text-lg font-medium">카메라 프리뷰 영역</p>
          </div>
        </section>
        <section className="space-y-4">
          <GlassPanel title="Capture" body="촬영 버튼, 타이머, 권한 상태" />
          <GlassPanel
            title="Analysis"
            body="촬영 후 후처리 또는 AI 분석 결과 카드"
          />
        </section>
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

function getRedirectTarget() {
  if (typeof window === 'undefined') {
    return '/main'
  }

  const redirectTo = new URLSearchParams(window.location.search).get('redirect')

  if (!redirectTo || !redirectTo.startsWith('/')) {
    return '/main'
  }

  return redirectTo
}
