import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Link,
  Outlet,
  redirect,
} from '@tanstack/react-router'
import { useEffect, useState, type ReactElement } from 'react'
import Camera from '@/app/Camera'
import Login from '@/app/Login'
import SignUp from '@/app/SignUp'
import { BottomNav } from '@/components/bottom-nav'
import { PageShell } from '@/components/page-shell'
import { ProfileCard } from '@/components/profile-card'
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
  const slides = [
    {
      title: '내가 원하는 헤어를\n마음껏 착용해 보아요.',
      imageSrc: '/icon/splash-01.svg',
      imageAlt: '헤어 가상 착용을 보여주는 카메라 일러스트',
    },
    {
      title: '인기있는 스타일과 함께\n디자이너와 소통해요',
      imageSrc: '/icon/splash-02.svg',
      imageAlt: '인기 헤어 스타일과 디자이너 소통을 보여주는 일러스트',
    },
    {
      title: '다양한 종류의 헤어를\n찾아볼 수 있어요',
      imageSrc: '/icon/splash-03.svg',
      imageAlt: '다양한 헤어 스타일 탐색을 보여주는 일러스트',
    },
  ] as const

  const [activeSlide, setActiveSlide] = useState(0)

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setActiveSlide((prev) => (prev + 1) % slides.length)
    }, 3000)

    return () => window.clearInterval(intervalId)
  }, [slides.length])

  const currentSlide = slides[activeSlide]

  return (
    <main className="app-frame-page flex min-h-dvh flex-col overflow-hidden bg-bg-primary px-3 pt-16 pb-8 text-[#2f2f2f]">
      <div className="mx-auto flex w-full max-w-[390px] flex-1 flex-col">
        <section className="flex flex-1 flex-col items-center">
          <h1 className="whitespace-pre-line px-8 text-center text-[20px] leading-[1.35] font-semibold tracking-[-0.03em] text-[#2f2f2f]">
            {currentSlide.title}
          </h1>

          <div className="mt-[92px] flex w-full justify-center px-5">
            <img
              src={currentSlide.imageSrc}
              alt={currentSlide.imageAlt}
              width={398}
              height={320}
              loading="eager"
              decoding="async"
              className="h-auto w-full max-w-[398px] object-contain"
              draggable={false}
            />
          </div>

          <div
            aria-label={`현재 ${activeSlide + 1}번째 온보딩 슬라이드`}
            className="mt-[30px] flex items-center justify-center gap-[7px]"
          >
            {slides.map((slide, index) => (
              <span
                key={slide.imageSrc}
                className={`block size-[10px] rounded-full transition-colors ${
                  index === activeSlide ? 'bg-[#f39ca6]' : 'bg-[#e3e3e8]'
                }`}
              />
            ))}
          </div>
        </section>

        <div className="pt-10">
          <Button
            asChild
            className="h-14 w-full rounded-[8px] bg-[#ea7589] px-6 py-4 text-base font-medium leading-[1.4] text-[#f2f2f7] hover:bg-[#e1637b]"
          >
            <Link to="/auth/login">헤어 어때 시작하기</Link>
          </Button>
        </div>
      </div>
    </main>
  )
}

function AuthLayout() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-primary-100 px-6 py-10">
      <div className="w-full max-w-md">
        <Outlet />
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
