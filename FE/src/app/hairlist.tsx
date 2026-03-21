import { useNavigate, useSearch } from '@tanstack/react-router'
import { ChevronLeft } from 'lucide-react'
import { useState } from 'react'

import { Header } from '@/components/header'
import { CategoryCard } from '@/components/ui/category-card'
import { HairStyleCard } from '@/components/ui/hair-style-card'
import { useCategoryCardList } from '@/hooks/Home/useCategoryCardList'
import { useCategoryList } from '@/hooks/Home/useCategoryList'
import { postHairClick } from '@/lib/hair-click'

export default function HairList() {
  const navigate = useNavigate()
  const { data: categoryData, isLoading: isCategoryLoading } = useCategoryList()
  const apiCategories = categoryData?.categoryList || []
  const { category: selectedCategory } = useSearch({ from: '/hairlist' })
  const [likedIds, setLikedIds] = useState<Record<string, boolean>>({})

  const activeCategory = selectedCategory ?? ''

  const { data: cardListData, isLoading: isCardListLoading } =
    useCategoryCardList(activeCategory || undefined)
  const filteredStyles = cardListData?.cardList || []

  function handleCategoryClick(categoryId: string) {
    navigate({
      to: '/hairlist',
      search: { category: categoryId || undefined },
    })
  }

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
              : apiCategories.map((category) => (
                  <button
                    key={category.categoryID}
                    type="button"
                    className="shrink-0"
                    onClick={() => handleCategoryClick(category.categoryID)}
                  >
                    <CategoryCard
                      label={category.categoryName}
                      imageSrc={category.image}
                      active={activeCategory === category.categoryID}
                    />
                  </button>
                ))}
          </div>
        </section>

        <section className="mt-4">
          {isCardListLoading ? (
            <div className="grid grid-cols-2 gap-x-3 gap-y-4">
              {[1, 2, 3, 4].map((key) => (
                <div
                  key={key}
                  className="h-[240px] w-full rounded-xl bg-neutral-200 animate-pulse"
                />
              ))}
            </div>
          ) : filteredStyles.length > 0 ? (
            <div className="grid grid-cols-2 gap-x-3 gap-y-4">
              {filteredStyles.map((style) => (
                <HairStyleCard
                  key={style.hairID}
                  hairId={style.hairID}
                  imageSrc={style.image}
                  imageAlt={style.hairName}
                  title={style.hairName}
                  subtitle={style.hookText}
                  liked={likedIds[style.hairID.toString()] ?? style.liked}
                  className="w-full"
                  onLikeToggle={() =>
                    setLikedIds((prev) => ({
                      ...prev,
                      [style.hairID.toString()]: !(
                        prev[style.hairID.toString()] ?? style.liked
                      ),
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
