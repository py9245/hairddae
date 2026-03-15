import type { Meta, StoryObj } from '@storybook/react-vite'
import { useEffect, useMemo, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRouteWithContext,
  createRoute,
  createRouter,
} from '@tanstack/react-router'
import SignUp from '@/app/SignUp'
import Login from '@/app/Login'
import { auth } from '@/lib/auth'

const rootRoute = createRootRouteWithContext<{ auth: typeof auth }>()({
  component: () => <Outlet />,
})

const authRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'auth',
  component: () => (
        <Outlet />
  ),
})

const signupRoute = createRoute({
  getParentRoute: () => authRoute,
  path: 'signup',
  component: SignUp,
})

const loginRoute = createRoute({
  getParentRoute: () => authRoute,
  path: 'login',
  component: Login,
})

const routeTree = rootRoute.addChildren([
  authRoute.addChildren([signupRoute, loginRoute]),
])

function MockFetchProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    const originalFetch = window.fetch

    async function mockedFetch(input: RequestInfo | URL, init?: RequestInit) {
      const url = typeof input === 'string' ? input : input.toString()
      const method = init?.method ?? (typeof input !== 'string' && 'method' in input ? (input as Request).method : 'GET')

      if (url.endsWith('/api/accounts/signin/') && method.toUpperCase() === 'POST') {
        let payload: any = {}
        try {
          const raw = (init?.body ?? (typeof input !== 'string' && 'body' in input ? (input as Request).body : undefined)) as any
          const text = typeof raw === 'string' ? raw : (typeof raw?.getReader === 'function' ? await new Response(raw).text() : '')
          payload = text ? JSON.parse(text) : {}
        } catch {
          payload = {}
        }

        const {
          userID,
          password,
          passwordCheck,
        } = payload as { userID?: string; password?: string; passwordCheck?: string }

        if (
          userID === 'qwer1234' &&
          password === 'qwer1234!' &&
          passwordCheck === 'qwer1234!'
        ) {
          const body = {
            message: '회원가입 완료',
            userID: 'qwer1234',
          }
          return new Response(JSON.stringify(body), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        }

        return new Response(
          JSON.stringify({ message: '회원가입에 실패했습니다.' }),
          { status: 400, headers: { 'Content-Type': 'application/json' } },
        )
      }

      return originalFetch(input as any, init)
    }

    window.fetch = mockedFetch as typeof window.fetch
    return () => {
      window.fetch = originalFetch
    }
  }, [])

  return <>{children}</>
}

function Providers() {
  const queryClient = useMemo(() => new QueryClient(), [])
  const router = useMemo(
    () =>
      createRouter({
        routeTree,
        context: { auth },
        history: createMemoryHistory({ initialEntries: ['/auth/signup'] }),
        defaultPreload: 'intent',
      }),
    [],
  )

  return (
    <QueryClientProvider client={queryClient}>
      <MockFetchProvider>
        <RouterProvider router={router} />
      </MockFetchProvider>
    </QueryClientProvider>
  )
}

const meta = {
  title: 'Pages/SignUp',
  component: SignUp,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
  render: () => <Providers />,
} satisfies Meta<typeof SignUp>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
