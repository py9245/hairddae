import { useNavigate } from '@tanstack/react-router'

import { Header } from '@/components/header'
import { Button } from '@/components/ui/button'
import { auth } from '@/lib/auth'

export default function MyPage() {
  const navigate = useNavigate()

  async function handleLogout() {
    await auth.logout()
    await navigate({ to: '/' })
  }

  return (
    <main className="app-frame-page bg-bg-primary px-4 pt-3">
      <div className="mx-auto flex w-full max-w-[390px] flex-col">
        <Header label="내정보" />

        <div className="mt-8 rounded-3xl bg-card p-6">
          <Button variant="logout" size="full" onClick={handleLogout}>
            로그아웃
          </Button>
        </div>
      </div>
    </main>
  )
}
