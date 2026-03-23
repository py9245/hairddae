import { useNavigate, useSearch } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'

import { HairListBottomNav } from '@/components/hair-list-bottom-nav'
import { Header } from '@/components/header'
import { CategoryCard } from '@/components/ui/category-card'
import { CategorySkeleton } from '@/components/ui/category-skeleton'
import { HairStyleCard } from '@/components/ui/hair-style-card'
import { HairStyleSkeleton } from '@/components/ui/hair-style-skeleton'
import { useCategoryCardList } from '@/hooks/Home/useCategoryCardList'
import { useCategoryList } from '@/hooks/Home/useCategoryList'
import { postHairClick } from '@/lib/hair-click'
import { cn } from '@/lib/utils'

const HAIR_LIST_BACK_EXIT_MS = 220

export default function HairList() {
  const navigate = useNavigate()
  const { data: categoryData, isLoading: isCategoryLoading } = useCategoryList()
  const apiCategories = categoryData?.categoryList || []
  const { category: selectedCategory } = useSearch({ from: '/hairlist' })
  const [likedIds, setLikedIds] = useState<Record<string, boolean>>({})
  const [isLeaving, setIsLeaving] = useState(false)
  const backExitTimeoutRef = useRef<number | null>(null)

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

  function handleBack() {
    if (isLeaving) {
      return
    }

    setIsLeaving(true)
    backExitTimeoutRef.current = window.setTimeout(() => {
      backExitTimeoutRef.current = null
      navigate({ to: '/main' })
    }, HAIR_LIST_BACK_EXIT_MS)
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

  useEffect(() => {
    return () => {
      if (backExitTimeoutRef.current !== null) {
        window.clearTimeout(backExitTimeoutRef.current)
      }
    }
  }, [])

  return (
    <main
      className={cn(
        'app-frame-page relative h-full overflow-y-auto bg-bg-primary pb-[108px] text-text-warm-500',
        isLeaving && 'animate-hair-list-page-out',
      )}
    >
      <Header
        centerContent={
          <h1 className="text-base font-semibold text-text-warm-600">
            헤어 스타일
          </h1>
        }
      />

      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-16">
        <section className="mt-2 overflow-x-auto pb-1">
          <div className="flex min-w-max items-start gap-3">
            {isCategoryLoading ? (
              <CategorySkeleton count={6} />
            ) : (
              apiCategories.map((category) => (
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
              ))
            )}
          </div>
        </section>

        <section className="mt-4">
          {isCardListLoading ? (
            <HairStyleSkeleton count={4} />
          ) : filteredStyles.length > 0 ? (
            <div className="grid grid-cols-2 gap-x-3 gap-y-4">
              {filteredStyles.map((style) => (
                <HairStyleCard
                  key={style.hairID}
                  hairId={style.hairID}
                  imageSrc={style.image}
                  imageAlt={style.hairName}
                  hairName={style.hairName}
                  hookText={style.hookText}
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

      <HairListBottomNav
        isExiting={isLeaving}
        onBack={handleBack}
        onNavigate={(to) => navigate({ to })}
      />
    </main>
  )
}
