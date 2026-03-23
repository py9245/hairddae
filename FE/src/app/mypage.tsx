import { useNavigate } from '@tanstack/react-router'

import { Header } from '@/components/header'
import { ProfileCard, ProfileCardSkeleton } from '@/components/profile-card'
import { HairStyleCard } from '@/components/ui/hair-style-card'
import { useMe } from '@/hooks/Auth/useMe'
import { useLikeList } from '@/hooks/MyPage/useLikeList'
import { auth } from '@/lib/auth'

export default function MyPage() {
  const navigate = useNavigate()
  const { data: meData, isLoading } = useMe()
  const { data: likeData, isLoading: isLikeLoading } = useLikeList()

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

        <div className="mt-8">
          <h2 className="mb-3 text-base font-bold text-text-primary">찜한 스타일</h2>
          {isLikeLoading ? (
            <div className="flex gap-3 overflow-x-auto pb-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-[227px] w-[170px] shrink-0 animate-pulse rounded-[14px] bg-primary-150"
                />
              ))}
            </div>
          ) : likeData && likeData.likeList.length > 0 ? (
            <div className="flex gap-3 overflow-x-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {likeData.likeList.map((item) => (
                <div key={item.hairID} className="shrink-0">
                  <HairStyleCard
                    hairId={item.hairID}
                    imageSrc={item.image}
                    imageAlt={item.hairName}
                    hairName={item.hairName}
                    hookText={item.hookText}
                    liked={item.liked}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-3xl bg-card p-6 text-center text-sm text-text-warm-300">
              찜한 스타일이 없습니다.
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
