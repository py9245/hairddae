import { useMutation, useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { useCategoryList } from '@/hooks/Home/useCategoryList'
import {
  type DesignerCategoryRequest,
  getDesignerSpecialties,
  submitDesignerCategoryList,
  updateDesignerCategoryList,
} from '@/lib/mypage'

type DesignerCategoryDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

function isAllCategory(categoryName: string) {
  return categoryName.trim() === '전체'
}

export function DesignerCategoryDialog({
  open,
  onOpenChange,
}: DesignerCategoryDialogProps) {
  const { data, isLoading, isError } = useCategoryList()
  const {
    data: specialtiesData,
    isLoading: isSpecialtiesLoading,
    isError: isSpecialtiesError,
  } = useQuery({
    queryKey: ['designerSpecialties'],
    queryFn: getDesignerSpecialties,
    enabled: open,
  })
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  const mutation = useMutation({
    mutationFn: ({
      hasExistingSpecialties,
      payload,
    }: {
      hasExistingSpecialties: boolean
      payload: DesignerCategoryRequest
    }) =>
      hasExistingSpecialties
        ? updateDesignerCategoryList(payload)
        : submitDesignerCategoryList(payload),
  })
  const resetDesignerCategory = mutation.reset

  const categories = data?.categoryList ?? []
  const selectableCategoryNames = useMemo(
    () =>
      categories
        .map((category) => category.categoryName)
        .filter((categoryName) => !isAllCategory(categoryName)),
    [categories],
  )
  const isSubmitDisabled = selectedCategories.length === 0 || mutation.isPending

  const selectedLabel = useMemo(() => {
    if (selectedCategories.length === 0) {
      return '선택한 카테고리가 없습니다.'
    }

    return selectedCategories.join(', ')
  }, [selectedCategories])

  useEffect(() => {
    if (!open) {
      setSelectedCategories([])
      resetDesignerCategory()
      return
    }

    if (!specialtiesData) {
      return
    }

    const nextSelected = specialtiesData.specialties
      .map((specialty) => specialty.categoryName)
      .filter((categoryName) => selectableCategoryNames.includes(categoryName))

    setSelectedCategories(nextSelected)
  }, [open, resetDesignerCategory, selectableCategoryNames, specialtiesData])

  if (!open) {
    return null
  }

  function handleClose() {
    if (mutation.isPending) {
      return
    }

    onOpenChange(false)
  }

  function handleToggleCategory(categoryName: string) {
    if (isAllCategory(categoryName)) {
      setSelectedCategories((current) =>
        current.length === selectableCategoryNames.length
          ? []
          : selectableCategoryNames,
      )
      return
    }

    setSelectedCategories((current) =>
      current.includes(categoryName)
        ? current.filter((item) => item !== categoryName)
        : [...current, categoryName],
    )
  }

  function handleSubmit() {
    if (isSubmitDisabled) {
      return
    }

    mutation.mutate(
      {
        hasExistingSpecialties: (specialtiesData?.specialties.length ?? 0) > 0,
        payload: {
          categoryIds: selectedCategories,
        },
      },
      {
        onSuccess: () => {
          onOpenChange(false)
        },
      },
    )
  }

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="designer-category-title"
        className="pointer-events-auto w-full max-w-[360px] rounded-[24px] bg-card p-6 shadow-[0_20px_40px_rgba(15,23,42,0.18)]"
      >
        <div className="relative pr-10 text-left">
          <button
            type="button"
            aria-label="자신있는 헤어 등록 모달 닫기"
            className="absolute -right-1 -top-1 inline-flex h-9 w-9 items-center justify-center rounded-full text-text-warm-400 transition hover:bg-neutral-100 hover:text-text-dark"
            onClick={handleClose}
            disabled={mutation.isPending}
          >
            <X className="h-5 w-5" />
          </button>

          <h2
            id="designer-category-title"
            className="text-xl font-bold text-text-warm-600"
          >
            자신있는 헤어 등록
          </h2>
          <p className="mt-2 text-sm leading-6 text-text-warm-400">
            카테고리를 선택한 뒤 등록하면
            <br />
            디자이너 프로필에 반영할 수 있습니다.
          </p>
        </div>

        <div className="mt-5 rounded-2xl bg-primary-100/50 p-4">
          <p className="text-xs font-semibold text-primary-300">
            선택한 카테고리
          </p>
          <p className="mt-2 text-sm leading-6 text-text-dark">
            {selectedLabel}
          </p>
        </div>

        <div className="mt-5">
          <p className="text-sm font-semibold text-text-dark">카테고리 추가</p>
          {isLoading || isSpecialtiesLoading ? (
            <div className="mt-3 grid grid-cols-2 gap-2">
              {[0, 1, 2, 3].map((item) => (
                <div
                  key={item}
                  className="h-11 animate-pulse rounded-2xl bg-primary-100"
                />
              ))}
            </div>
          ) : isError || isSpecialtiesError ? (
            <p className="mt-3 text-sm text-error" role="alert">
              카테고리 정보를 불러오지 못했습니다.
            </p>
          ) : (
            <div className="mt-3 grid max-h-[260px] grid-cols-2 gap-2 overflow-y-auto pr-1">
              {categories.map((category) => {
                const active = isAllCategory(category.categoryName)
                  ? selectableCategoryNames.length > 0 &&
                    selectedCategories.length === selectableCategoryNames.length
                  : selectedCategories.includes(category.categoryName)

                return (
                  <button
                    key={category.categoryID}
                    type="button"
                    className={[
                      'rounded-2xl border px-4 py-3 text-sm font-semibold transition',
                      active
                        ? 'border-primary-300 bg-primary-100 text-primary-300'
                        : 'border-neutral-200 bg-white text-text-dark hover:border-primary-200 hover:bg-primary-100/40',
                    ].join(' ')}
                    onClick={() => handleToggleCategory(category.categoryName)}
                    aria-pressed={active}
                  >
                    {category.categoryName}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {mutation.isError ? (
          <p className="mt-4 text-sm text-error" role="alert">
            자신있는 헤어 등록 중 오류가 발생했습니다.
          </p>
        ) : null}

        <div className="mt-5 flex gap-2">
          <Button
            variant="outline"
            className="h-12 flex-1 rounded-xl"
            onClick={handleClose}
            disabled={mutation.isPending}
          >
            취소
          </Button>
          <Button
            variant="login"
            className="h-12 flex-1 rounded-xl bg-primary-200 text-text-dark hover:bg-primary-200"
            onClick={handleSubmit}
            disabled={isSubmitDisabled}
          >
            {mutation.isPending ? '등록 중...' : '자신있는 헤어 등록'}
          </Button>
        </div>
      </div>
    </div>
  )
}
