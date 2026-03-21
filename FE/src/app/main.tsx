import { useNavigate } from '@tanstack/react-router'
import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

import { Header } from '@/components/header'
import { CustomRankBanner } from '@/components/home/custom-rank-banner'
import { CategoryCard } from '@/components/ui/category-card'
import { HairStyleCard } from '@/components/ui/hair-style-card'
import { SortToggle } from '@/components/ui/sort-toggle'
import { useMe } from '@/hooks/Auth/useMe'
import { useCategoryList } from '@/hooks/Home/useCategoryList'
import { useNormalRank } from '@/hooks/Home/useNormalRank'
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

  const [likedIds, setLikedIds] = useState<Record<string, boolean>>({
    'style-1': true,
    'style-2': true,
    'style-3': true,
    'style-4': true,
  })
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
    <main className="app-frame-page h-full overflow-y-auto bg-neutral-500 pb-[108px] text-text-warm-500">
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
              {isCategoryLoading
                ? [1, 2, 3, 4, 5, 6].map((key) => (
                    <div
                      key={key}
                      className="flex w-[44px] shrink-0 flex-col items-center gap-2"
                    >
                      <div className="h-[44px] w-[44px] rounded-[8px] border border-transparent bg-neutral-200 animate-pulse" />
                      <div className="h-3 w-8 rounded-sm bg-neutral-200 animate-pulse" />
                    </div>
                  ))
                : categories.map((category) => (
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
                  ))}
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

            <SortToggle
              options={sortOptions}
              value={sortValue}
              onChange={setSortValue}
            />
          </div>

          {isNormalRankLoading ? (
            <div className="grid grid-cols-2 gap-x-3 gap-y-4">
              {[1, 2, 3, 4].map((key) => (
                <div
                  key={key}
                  className="h-[240px] w-full rounded-xl bg-neutral-200 animate-pulse"
                />
              ))}
            </div>
          ) : (
            <div className="mt-4 grid grid-cols-2 gap-x-3 gap-y-4">
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
                  onLikeToggle={() =>
                    setLikedIds((prev) => ({
                      ...prev,
                      [card.hairID.toString()]: !(
                        prev[card.hairID.toString()] ?? card.liked
                      ),
                    }))
                  }
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
