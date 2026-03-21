import { useNavigate, useSearch } from '@tanstack/react-router'
import { ChevronLeft } from 'lucide-react'
import { useState } from 'react'

import { Header } from '@/components/header'
import { CategoryCard } from '@/components/ui/category-card'
import { HairStyleCard } from '@/components/ui/hair-style-card'
import { postHairClick } from '@/lib/hair-click'

type Category = {
  id: string
  label: string
  imageSrc?: string
}

type HairStyle = {
  id: string
  hairId: number
  title: string
  subtitle: string
  imageSrc: string
  imageAlt: string
  categoryId: string
}

const categories: Category[] = [
  { id: '', label: '전체' },
  { id: 'short', label: '단발', imageSrc: '/hiar-style/style-01-image.png' },
  { id: 'layered', label: '숏컷', imageSrc: '/hiar-style/style-02-image.png' },
  { id: 'bob', label: '단발펌', imageSrc: '/hiar-style/style-01-image.png' },
  { id: 'perm', label: '숏컷', imageSrc: '/hiar-style/style-02-image.png' },
  { id: 'cut', label: '단발', imageSrc: '/hiar-style/style-01-image.png' },
  { id: 'trend', label: '숏컷', imageSrc: '/hiar-style/style-02-image.png' },
]

const hairStyles: HairStyle[] = [
  {
    id: 'style-1',
    hairId: 1,
    title: '트렌디한\n쇼트 컷',
    subtitle: '숏컷',
    imageSrc: '/hiar-style/style-01-image.png',
    imageAlt: '트렌디한 쇼트 컷 예시',
    categoryId: 'short',
  },
  {
    id: 'style-2',
    hairId: 2,
    title: '우아한\n레이어드 헤어',
    subtitle: '레이어드 컷',
    imageSrc: '/hiar-style/style-02-image.png',
    imageAlt: '우아한 레이어드 헤어 예시',
    categoryId: 'layered',
  },
  {
    id: 'style-3',
    hairId: 3,
    title: '러블리\n단발 펌',
    subtitle: '단발펌',
    imageSrc: '/hiar-style/style-01-image.png',
    imageAlt: '러블리 단발 펌 예시',
    categoryId: 'bob',
  },
  {
    id: 'style-4',
    hairId: 4,
    title: '시크한\n숏컷 스타일',
    subtitle: '숏컷',
    imageSrc: '/hiar-style/style-02-image.png',
    imageAlt: '시크한 숏컷 스타일 예시',
    categoryId: 'short',
  },
  {
    id: 'style-5',
    hairId: 5,
    title: '내추럴\n단발 스타일',
    subtitle: '단발',
    imageSrc: '/hiar-style/style-01-image.png',
    imageAlt: '내추럴 단발 스타일 예시',
    categoryId: 'cut',
  },
  {
    id: 'style-6',
    hairId: 6,
    title: '볼륨감 있는\n단발 펌',
    subtitle: '단발펌',
    imageSrc: '/hiar-style/style-02-image.png',
    imageAlt: '볼륨감 있는 단발 펌 예시',
    categoryId: 'perm',
  },
]

export default function HairList() {
  const navigate = useNavigate()
  const { category: selectedCategory } = useSearch({ from: '/hairlist' })
  const [likedIds, setLikedIds] = useState<Record<string, boolean>>({})

  const activeCategory = selectedCategory ?? ''
  const filteredStyles =
    activeCategory === ''
      ? hairStyles
      : hairStyles.filter((style) => style.categoryId === activeCategory)

  function handleCategoryClick(categoryId: string) {
    navigate({
      to: '/hairlist',
      search: { category: categoryId || undefined },
    })
  }

  async function handleApply(hairId: number) {
    try {
      await postHairClick(hairId)
    } catch (error) {
      console.error('hair click failed:', error)
    }

    await navigate({
      to: '/camera',
      search: { applyLatest: true },
    })
  }

  return (
    <main className="app-frame-page h-full overflow-y-auto bg-neutral-500 text-text-warm-500">
      <Header
        leftAction={
          <button
            type="button"
            onClick={() => navigate({ to: '/main' })}
            aria-label="뒤로 가기"
          >
            <ChevronLeft className="size-6 text-text-warm-500" />
          </button>
        }
        centerContent={
          <h1 className="text-base font-semibold text-text-warm-600">
            헤어 스타일
          </h1>
        }
      />

      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-16">
        <section className="mt-2 overflow-x-auto pb-1">
          <div className="flex min-w-max items-start gap-3">
            {categories.map((category) => (
              <button
                key={category.id}
                type="button"
                className="shrink-0"
                onClick={() => handleCategoryClick(category.id)}
              >
                <CategoryCard
                  label={category.label}
                  imageSrc={category.imageSrc}
                  active={activeCategory === category.id}
                />
              </button>
            ))}
          </div>
        </section>

        <section className="mt-4">
          {filteredStyles.length > 0 ? (
            <div className="grid grid-cols-2 gap-x-3 gap-y-4">
              {filteredStyles.map((style) => (
                <HairStyleCard
                  key={style.id}
                  hairId={style.hairId}
                  imageSrc={style.imageSrc}
                  imageAlt={style.imageAlt}
                  title={style.title}
                  subtitle={style.subtitle}
                  liked={likedIds[style.id] ?? false}
                  className="w-full"
                  onLikeToggle={() =>
                    setLikedIds((prev) => ({
                      ...prev,
                      [style.id]: !prev[style.id],
                    }))
                  }
                  onApply={handleApply}
                />
              ))}
            </div>
          ) : (
            <p className="mt-10 text-center text-sm text-text-warm-200">
              해당 카테고리의 헤어 스타일이 없어요.
            </p>
          )}
        </section>
      </div>
    </main>
  )
}
