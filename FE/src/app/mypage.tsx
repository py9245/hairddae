import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { Header } from '@/components/header'
import { ProfileCard, ProfileCardSkeleton } from '@/components/profile-card'
import { HairStyleCard } from '@/components/ui/hair-style-card'
import { useMe } from '@/hooks/Auth/useMe'
import { useToggleLike } from '@/hooks/Home/useToggleLike'
import { useLikeList } from '@/hooks/MyPage/useLikeList'
import { auth } from '@/lib/auth'

export default function MyPage() {
  const navigate = useNavigate()
  const { data: meData, isLoading } = useMe()
  const { data: likeData, isLoading: isLikeLoading } = useLikeList()
  const [likedIds, setLikedIds] = useState<Record<string, boolean>>({})
  const { mutate: toggleLike } = useToggleLike()
  const visibleLikeList =
    likeData?.likeList.filter(
      (item) => likedIds[item.hairID.toString()] ?? item.liked,
    ) ?? []

  async function handleLogout() {
    await auth.logout()
    await navigate({ to: '/' })
  }

  return (
    <main className="app-frame-page h-full overflow-y-auto bg-bg-primary pb-[108px]">
      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-3">
        <Header label="내정보" className="px-0 pb-3 pt-2" />
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
          <h2 className="mb-3 text-base font-bold text-text-primary">
            찜한 스타일
          </h2>
          {isLikeLoading ? (
            <div className="flex gap-3 overflow-x-auto pb-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-[227px] w-[170px] shrink-0 animate-pulse rounded-[14px] bg-primary-150"
                />
              ))}
            </div>
          ) : visibleLikeList.length > 0 ? (
            <div className="flex gap-3 overflow-x-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {visibleLikeList.map((item) => (
                <div key={item.hairID} className="shrink-0">
                  <HairStyleCard
                    hairId={item.hairID}
                    imageSrc={item.image}
                    imageAlt={item.hairName}
                    hairName={item.hairName}
                    hookText={item.hookText}
                    liked={likedIds[item.hairID.toString()] ?? item.liked}
                    onLikeToggle={() => {
                      const currentLiked =
                        likedIds[item.hairID.toString()] ?? item.liked
                      setLikedIds((prev) => ({
                        ...prev,
                        [item.hairID.toString()]: !currentLiked,
                      }))
                      toggleLike(
                        { hairId: item.hairID, currentLiked },
                        {
                          onSuccess: (data) => {
                            setLikedIds((prev) => ({
                              ...prev,
                              [data.hairID.toString()]: data.liked,
                            }))
                          },
                          onError: () => {
                            setLikedIds((prev) => ({
                              ...prev,
                              [item.hairID.toString()]: currentLiked,
                            }))
                          },
                        },
                      )
                    }}
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
