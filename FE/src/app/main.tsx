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
import { postHairClick } from '@/lib/hair-click'

type RecommendationCard = {
  id: string
  hairId: number
  title: string
  subtitle: string
  imageSrc: string
  imageAlt: string
  rank: number
  createdAt: string
  categoryId: string
}

type SortValue = 'popular' | 'latest'

const sortOptions = [
  { value: 'popular', label: '인기순' },
  { value: 'latest', label: '최신순' },
] as const

const recommendations: RecommendationCard[] = [
  {
    id: 'style-1',
    hairId: 1,
    title: '트렌디한\n쇼트 컷',
    subtitle: '숏컷',
    imageSrc: '/hiar-style/style-01-image.png',
    imageAlt: '트렌디한 쇼트 컷 예시',
    rank: 2,
    createdAt: '2026-03-19T09:00:00+09:00',
    categoryId: 'short',
  },
  {
    id: 'style-2',
    hairId: 2,
    title: '우아한\n레이어드 헤어',
    subtitle: '레이어드 컷',
    imageSrc: '/hiar-style/style-02-image.png',
    imageAlt: '우아한 레이어드 헤어 예시',
    rank: 1,
    createdAt: '2026-03-18T09:00:00+09:00',
    categoryId: 'layered',
  },
  {
    id: 'style-3',
    hairId: 3,
    title: '러블리\n단발 펌',
    subtitle: '단발펌',
    imageSrc: '/hiar-style/style-01-image.png',
    imageAlt: '러블리 단발 펌 예시',
    rank: 4,
    createdAt: '2026-03-17T09:00:00+09:00',
    categoryId: 'bob',
  },
  {
    id: 'style-4',
    hairId: 4,
    title: '시크한\n숏컷 스타일',
    subtitle: '숏컷',
    imageSrc: '/hiar-style/style-02-image.png',
    imageAlt: '시크한 숏컷 스타일 예시',
    rank: 3,
    createdAt: '2026-03-20T09:00:00+09:00',
    categoryId: 'short',
  },
]

export default function Main() {
  const navigate = useNavigate()
  const { data: meData } = useMe()

  const { data: categoryData, isLoading: isCategoryLoading } = useCategoryList()
  const categories = categoryData?.categoryList || []

  const [likedIds, setLikedIds] = useState<Record<string, boolean>>({
    'style-1': true,
    'style-2': true,
    'style-3': true,
    'style-4': true,
  })
  const [sortValue, setSortValue] = useState<SortValue>('popular')

  const sortedRecommendations = [...recommendations].sort((left, right) => {
    if (sortValue === 'latest') {
      return (
        new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
      )
    }

    return left.rank - right.rank
  })

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

          <div className="mt-4 grid grid-cols-2 gap-x-3 gap-y-4">
            {sortedRecommendations.map((card) => (
              <HairStyleCard
                key={card.id}
                hairId={card.hairId}
                imageSrc={card.imageSrc}
                imageAlt={card.imageAlt}
                hairName={card.title}
                hookText={card.subtitle}
                liked={likedIds[card.id] ?? false}
                className="w-full"
                onLikeToggle={() =>
                  setLikedIds((prev) => ({
                    ...prev,
                    [card.id]: !prev[card.id],
                  }))
                }
                onApply={handleApply}
              />
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}
