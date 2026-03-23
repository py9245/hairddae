import { useNavigate } from '@tanstack/react-router'
import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

import { Header } from '@/components/header'
import { CustomRankBanner } from '@/components/home/custom-rank-banner'
import { CategoryCard } from '@/components/ui/category-card'
import { CategorySkeleton } from '@/components/ui/category-skeleton'
import { HairStyleCard } from '@/components/ui/hair-style-card'
import { HairStyleSkeleton } from '@/components/ui/hair-style-skeleton'
import { SortToggle } from '@/components/ui/sort-toggle'
import { SortToggleSkeleton } from '@/components/ui/sort-toggle-skeleton'
import { useMe } from '@/hooks/Auth/useMe'
import { useCategoryList } from '@/hooks/Home/useCategoryList'
import { useNormalRank } from '@/hooks/Home/useNormalRank'
import { useToggleLike } from '@/hooks/Home/useToggleLike'
import { postHairClick } from '@/lib/hair-click'

type SortValue = 'popular' | 'latest'

const sortOptions = [
  { value: 'popular', label: '인기순' },
  { value: 'latest', label: '최신순' },
] as const

export default function Main() {
  const navigate = useNavigate()
  const { data: meData } = useMe()
  const { data: normalRankData, isLoading: isNormalRankLoading } =
    useNormalRank()

  const { data: categoryData, isLoading: isCategoryLoading } = useCategoryList()
  const categories = categoryData?.categoryList || []

  const [likedIds, setLikedIds] = useState<Record<string, boolean>>({})
  const { mutate: toggleLike } = useToggleLike()
  const [sortValue, setSortValue] = useState<SortValue>('popular')

  const sortedRecommendations =
    sortValue === 'latest'
      ? (normalRankData?.latest ?? [])
      : (normalRankData?.best ?? [])

  async function handleApply(hairId: number) {
    let targetHairId = hairId

    try {
      const response = await postHairClick(hairId)
      targetHairId = response.hair_id
    } catch (error) {
      console.error('hair click failed:', error)
    }

    await navigate({
      to: '/camera',
      search: {
        applyLatest: true,
        hairId: targetHairId,
      },
    })
  }

  return (
    <main className="app-frame-page h-full overflow-y-auto bg-bg-primary pb-[108px] text-text-warm-500">
      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-3">
        <Header
          label="헤어때"
          labelClassName="text-primary-300 tracking-[-0.04em]"
          className="px-0 pb-3 pt-2"
        />

        <CustomRankBanner onApply={handleApply} />

        <section className="mt-4 flex items-start gap-2">
          <div className="min-w-0 flex-1 overflow-x-auto pb-1">
            <div className="flex min-w-max items-start gap-3">
              {isCategoryLoading ? (
                <CategorySkeleton count={6} />
              ) : (
                categories.map((category) => (
                  <button
                    key={category.categoryID}
                    type="button"
                    className="shrink-0"
                    onClick={() => {
                      navigate({
                        to: '/hairlist',
                        search: { category: category.categoryID },
                      })
                    }}
                  >
                    <CategoryCard
                      label={category.categoryName}
                      imageSrc={category.image}
                    />
                  </button>
                ))
              )}
            </div>
          </div>

          <button
            type="button"
            aria-label="카테고리 더보기"
            className="mt-3 flex size-6 shrink-0 items-center justify-center rounded-full bg-neutral-200 text-text-warm-100"
          >
            <ChevronDown className="size-4" />
          </button>
        </section>

        <section className="mt-4">
          <div className="flex items-center justify-between gap-3">

              <h2 className="text-24 leading-none font-extrabold tracking-[-0.05em] text-text-warm-600">
                {meData?.userID ? `${meData.userID}님` : '회원님'}을 위한 추천
                헤어
              </h2>

            {isNormalRankLoading ? (
              <SortToggleSkeleton />
            ) : (
              <SortToggle
                options={sortOptions}
                value={sortValue}
                onChange={setSortValue}
              />
            )}
          </div>

          {isNormalRankLoading ? (
            <HairStyleSkeleton count={4} className="mt-[10px] sm:mt-4" />
          ) : (
            <div className="mt-[10px] grid grid-cols-2 gap-x-3 gap-y-4 sm:mt-4">
              {sortedRecommendations.map((card) => (
                <HairStyleCard
                  key={card.hairID}
                  hairId={card.hairID}
                  imageSrc={card.image}
                  imageAlt={card.hairName}
                  hairName={card.hairName}
                  hookText={card.hookText}
                  liked={likedIds[card.hairID.toString()] ?? card.liked}
                  className="w-full"
                  onLikeToggle={() => {
                    const currentLiked =
                      likedIds[card.hairID.toString()] ?? card.liked
                    // 낙관적 업데이트
                    setLikedIds((prev) => ({
                      ...prev,
                      [card.hairID.toString()]: !currentLiked,
                    }))
                    toggleLike(
                      { hairId: card.hairID, currentLiked },
                      {
                        onSuccess: (data) => {
                          // 서버 응답으로 최종 상태 확정
                          setLikedIds((prev) => ({
                            ...prev,
                            [data.hairID.toString()]: data.liked,
                          }))
                        },
                        onError: () => {
                          // 실패 시 롤백
                          setLikedIds((prev) => ({
                            ...prev,
                            [card.hairID.toString()]: currentLiked,
                          }))
                        },
                      },
                    )
                  }}
                  onApply={handleApply}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
