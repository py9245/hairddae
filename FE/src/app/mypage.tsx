import { useNavigate } from '@tanstack/react-router'

import { Header } from '@/components/header'
import { ProfileCard, ProfileCardSkeleton } from '@/components/profile-card'
import { useMe } from '@/hooks/Auth/useMe'
import { auth } from '@/lib/auth'

export default function MyPage() {
  const navigate = useNavigate()
  const { data: meData, isLoading } = useMe()

  async function handleLogout() {
    await auth.logout()
    await navigate({ to: '/' })
  }

  return (
    <main className="app-frame-page bg-bg-primary px-4 pt-3">
      <div className="mx-auto flex w-full max-w-[390px] flex-col">
        <Header label="내정보" />
        <div className="mt-8">
          {isLoading ? (
            <ProfileCardSkeleton />
          ) : meData ? (
            <ProfileCard profile={meData} onLogout={handleLogout} />
          ) : (
            <div className="rounded-3xl bg-card p-6 text-center text-sm text-text-warm-300">
              로그인 정보가 없습니다.
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
