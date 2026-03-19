import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

import { Header } from '@/components/header'
import { CategoryCard } from '@/components/ui/category-card'
import { HairStyleCard } from '@/components/ui/hair-style-card'
import { cn } from '@/lib/utils'

type HeroCardProps = {
  title: string
  subtitle: string
  imageSrc: string
  imageAlt: string
  liked: boolean
  onLikeToggle: () => void
}

type FilterChipProps = {
  label: string
  active?: boolean
}

type MainCategory = {
  id: string
  label: string
  imageSrc: string
}

type RecommendationCard = {
  id: string
  title: string
  subtitle: string
  imageSrc: string
  imageAlt: string
}

const categories: MainCategory[] = [
  { id: 'short', label: '단발', imageSrc: '/hiar-style/style-01-image.png' },
  { id: 'layered', label: '숏컷', imageSrc: '/hiar-style/style-02-image.png' },
  { id: 'bob', label: '단발펌', imageSrc: '/hiar-style/style-01-image.png' },
  { id: 'perm', label: '숏컷', imageSrc: '/hiar-style/style-02-image.png' },
  { id: 'cut', label: '단발', imageSrc: '/hiar-style/style-01-image.png' },
  { id: 'trend', label: '숏컷', imageSrc: '/hiar-style/style-02-image.png' },
] as const

const recommendations: RecommendationCard[] = [
  {
    id: 'style-1',
    title: '우주 킹왕짱\n멋있는 헤어',
    subtitle: '레이어드 컷',
    imageSrc: '/hiar-style/style-02-image.png',
    imageAlt: '우주 킹왕짱 멋있는 헤어 예시',
  },
  {
    id: 'style-2',
    title: '우주 킹왕짱\n멋있는 헤어',
    subtitle: '레이어드 컷',
    imageSrc: '/hiar-style/style-02-image.png',
    imageAlt: '우주 킹왕짱 멋있는 헤어 예시',
  },
  {
    id: 'style-3',
    title: '우주 킹왕짱\n멋있는 헤어',
    subtitle: '레이어드 컷',
    imageSrc: '/hiar-style/style-02-image.png',
    imageAlt: '우주 킹왕짱 멋있는 헤어 예시',
  },
  {
    id: 'style-4',
    title: '우주 킹왕짱\n멋있는 헤어',
    subtitle: '레이어드 컷',
    imageSrc: '/hiar-style/style-02-image.png',
    imageAlt: '우주 킹왕짱 멋있는 헤어 예시',
  },
] as const

function HeroCard({
  title,
  subtitle,
  imageSrc,
  imageAlt,
  liked,
  onLikeToggle,
}: HeroCardProps) {
  const heartIconSrc = liked ? '/icon/heart-fill.svg' : '/icon/hair-empty.svg'
  const heartLabel = liked ? '찜 해제' : '찜하기'

  return (
    <article className="overflow-hidden rounded-[18px] border border-white/90 bg-white shadow-[0_14px_36px_rgba(227,194,194,0.32)]">
      <div className="p-[5px]">
        <img
          src={imageSrc}
          alt={imageAlt}
          className="h-[250px] w-full rounded-[14px] object-cover object-top"
          draggable={false}
        />
      </div>

      <div className="flex items-end justify-between gap-4 px-4 pb-4 pt-2">
        <div className="min-w-0">
          <h2 className="text-[17px] leading-[1.25] font-bold tracking-[-0.03em] text-[#5b4747]">
            {title}
          </h2>
          <p className="mt-1 text-[13px] text-[#8e8383]">{subtitle}</p>
        </div>

        <button
          type="button"
          aria-label={heartLabel}
          aria-pressed={liked}
          className="mb-1 flex size-8 shrink-0 items-center justify-center rounded-full bg-[#fff5f6] transition hover:bg-[#ffe8eb]"
          onClick={onLikeToggle}
        >
          <img
            src={heartIconSrc}
            alt=""
            aria-hidden="true"
            className="size-5"
          />
        </button>
      </div>
    </article>
  )
}

function FilterChip({ label, active = false }: FilterChipProps) {
  return (
    <button
      type="button"
      className={cn(
        'rounded-full px-3 py-1 text-[11px] font-semibold transition',
        active
          ? 'bg-[#ff8fa3] text-white shadow-[0_6px_16px_rgba(255,143,163,0.34)]'
          : 'bg-[#ffe7ec] text-[#ff8fa3]',
      )}
    >
      {label}
    </button>
  )
}

export default function Main() {
  const [heroLiked, setHeroLiked] = useState(true)
  const [likedIds, setLikedIds] = useState<Record<string, boolean>>({
    'style-1': true,
    'style-2': true,
    'style-3': true,
    'style-4': true,
  })
  const [activeCategoryId, setActiveCategoryId] = useState(categories[0].id)

  return (
    <main className="app-frame-page overflow-y-auto bg-[#f5f2ef] pb-[108px] text-[#4f4040]">
      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-3">
        <Header
          label="헤어때"
          labelClassName="text-primary-300 tracking-[-0.04em]"
          className="px-0 pb-3 pt-2"
        />

        <HeroCard
          title="봄의 시작을 알리는 여신머리"
          subtitle="레이어드컷"
          imageSrc="/component/image.png"
          imageAlt="메인 추천 헤어 예시"
          liked={heroLiked}
          onLikeToggle={() => setHeroLiked((prev) => !prev)}
        />

        <section className="mt-4 overflow-x-auto pb-1">
          <div className="flex min-w-max items-start gap-3">
            {categories.map((category) => (
              <button
                key={category.id}
                type="button"
                className="shrink-0"
                onClick={() => setActiveCategoryId(category.id)}
              >
                <CategoryCard
                  label={category.label}
                  imageSrc={category.imageSrc}
                  active={category.id === activeCategoryId}
                />
              </button>
            ))}
          </div>
        </section>

        <section className="mt-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-[24px] leading-none font-extrabold tracking-[-0.04em] text-[#3f3030]">
                김새피를 위한 추천 헤어
              </h2>
            </div>

            <div className="flex items-center gap-2">
              <FilterChip label="인기순" active />
              <FilterChip label="최신순" />
              <button
                type="button"
                aria-label="정렬 옵션 열기"
                className="mt-0.5 flex size-7 items-center justify-center rounded-full bg-[#e6e0db] text-[#7a6a6a]"
              >
                <ChevronDown className="size-4" />
              </button>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-x-3 gap-y-4">
            {recommendations.map((card) => (
              <HairStyleCard
                key={card.id}
                imageSrc={card.imageSrc}
                imageAlt={card.imageAlt}
                title={card.title}
                subtitle={card.subtitle}
                liked={likedIds[card.id] ?? false}
                className="w-full"
                onLikeToggle={() =>
                  setLikedIds((prev) => ({
                    ...prev,
                    [card.id]: !prev[card.id],
                  }))
                }
                onApply={() => {}}
              />
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}
