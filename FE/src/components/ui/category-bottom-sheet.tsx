import { X } from 'lucide-react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import { useEffect, useRef, useState } from 'react'

import { BottomSheet } from '@/components/ui/bottom-sheet'
import { CategoryCard } from '@/components/ui/category-card'
import { cn } from '@/lib/utils'

type Category = {
  categoryID: string
  categoryName: string
  image: string
}

type CategoryBottomSheetProps = {
  open: boolean
  onClose: () => void
  categories: Category[]
  selectedCategory: string
  onSelect: (categoryID: string) => void
  className?: string
}

const DRAG_DISMISS_THRESHOLD = 24
const DRAG_CLOSE_DURATION_MS = 180

export function CategoryBottomSheet({
  open,
  onClose,
  categories,
  selectedCategory,
  onSelect,
  className,
}: CategoryBottomSheetProps) {
  const shouldEnableCategoryScroll = categories.length > 6
  const activePointerIdRef = useRef<number | null>(null)
  const closeTimeoutRef = useRef<number | null>(null)
  const dragOffsetRef = useRef(0)
  const dragStartYRef = useRef(0)
  const [isDragging, setIsDragging] = useState(false)
  const [isClosingByDrag, setIsClosingByDrag] = useState(false)
  const [translateY, setTranslateY] = useState(0)

  function clearCloseTimeout() {
    if (closeTimeoutRef.current === null) {
      return
    }

    window.clearTimeout(closeTimeoutRef.current)
    closeTimeoutRef.current = null
  }

  function setDragOffset(nextOffset: number) {
    dragOffsetRef.current = nextOffset
    setTranslateY(nextOffset)
  }

  function resetDragState() {
    activePointerIdRef.current = null
    dragStartYRef.current = 0
    setIsDragging(false)
    setIsClosingByDrag(false)
    setDragOffset(0)
  }

  function handleDragDismiss() {
    setIsDragging(false)
    setIsClosingByDrag(true)
    setDragOffset(window.innerHeight)
    clearCloseTimeout()
    closeTimeoutRef.current = window.setTimeout(() => {
      clearCloseTimeout()
      onClose()
      resetDragState()
    }, DRAG_CLOSE_DURATION_MS)
  }

  function handleDragRelease() {
    if (dragOffsetRef.current >= DRAG_DISMISS_THRESHOLD) {
      handleDragDismiss()
      return
    }

    activePointerIdRef.current = null
    dragStartYRef.current = 0
    setIsDragging(false)
    setDragOffset(0)
  }

  function handleHeaderPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (isClosingByDrag) {
      return
    }

    if (event.pointerType === 'mouse' && event.button !== 0) {
      return
    }

    activePointerIdRef.current = event.pointerId
    dragStartYRef.current = event.clientY
    setIsDragging(true)
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function handleHeaderPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (
      !isDragging ||
      isClosingByDrag ||
      activePointerIdRef.current !== event.pointerId
    ) {
      return
    }

    const nextOffset = Math.max(0, event.clientY - dragStartYRef.current)
    setDragOffset(nextOffset)
  }

  function handleHeaderPointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    if (activePointerIdRef.current !== event.pointerId) {
      return
    }

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }

    handleDragRelease()
  }

  function handleHeaderPointerCancel(event: ReactPointerEvent<HTMLDivElement>) {
    if (activePointerIdRef.current !== event.pointerId) {
      return
    }

    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }

    activePointerIdRef.current = null
    dragStartYRef.current = 0
    setIsDragging(false)
    setDragOffset(0)
  }

  useEffect(() => {
    if (open) {
      return
    }

    if (closeTimeoutRef.current !== null) {
      window.clearTimeout(closeTimeoutRef.current)
      closeTimeoutRef.current = null
    }

    activePointerIdRef.current = null
    dragStartYRef.current = 0
    setIsDragging(false)
    setIsClosingByDrag(false)
    dragOffsetRef.current = 0
    setTranslateY(0)
  }, [open])

  useEffect(() => {
    return () => {
      if (closeTimeoutRef.current !== null) {
        window.clearTimeout(closeTimeoutRef.current)
      }
    }
  }, [])

  return (
    <BottomSheet
      isOpen={open}
      onClose={onClose}
      portalToAppFrame
      overlayClassName="-bottom-[104px] bg-black/18 backdrop-blur-[2px]"
      className={cn(
        'overflow-visible bg-transparent px-4 pb-0 pt-0 shadow-none',
        className,
      )}
      ariaLabel="카테고리 선택"
    >
      <div className="relative">
        <div
          className={cn(
            'relative mb-[94px] flex max-h-[calc(100dvh-6.5rem)] flex-col rounded-[32px] border border-white/70 bg-[#fffaf7] px-5 pb-5 pt-4 shadow-[0_-18px_40px_rgba(47,47,47,0.16)] will-change-transform',
            isDragging
              ? 'transition-none'
              : 'transition-transform duration-200 ease-out',
          )}
          style={{
            transform: `translateY(${translateY}px)`,
          }}
        >
          <div className="mb-4 flex items-start justify-between gap-3">
            <div
              className={cn(
                'space-y-1 touch-none select-none',
                isClosingByDrag
                  ? 'cursor-default'
                  : 'cursor-grab active:cursor-grabbing',
              )}
              onPointerDown={handleHeaderPointerDown}
              onPointerMove={handleHeaderPointerMove}
              onPointerUp={handleHeaderPointerUp}
              onPointerCancel={handleHeaderPointerCancel}
            >
              <h2 className="text-lg font-semibold tracking-[-0.03em] text-text-dark">
                어떤 카테고리를 살펴볼까요?
              </h2>
              <p className="text-sm text-text-warm-100">
                원하는 스타일 카테고리를 빠르게 골라볼 수 있어요.
              </p>
            </div>

            <button
              type="button"
              onClick={onClose}
              aria-label="카테고리 시트 닫기"
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-neutral-200/80 text-text-warm-400 transition hover:bg-neutral-200"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {categories.length > 0 ? (
            <div
              className={cn(
                'min-h-0 pt-2',
                shouldEnableCategoryScroll &&
                  'max-h-[292px] overflow-y-auto pr-1',
              )}
            >
              <div className="grid grid-cols-3 gap-x-5 gap-y-6">
                {categories.map((category) => {
                  const active = category.categoryID === selectedCategory

                  return (
                    <button
                      key={category.categoryID}
                      type="button"
                      aria-pressed={active}
                      onClick={() => onSelect(category.categoryID)}
                      className={cn(
                        'flex flex-col items-center rounded-[20px] px-2 py-1 transition',
                        active ? 'bg-primary-50' : 'hover:bg-white/70',
                      )}
                    >
                      <CategoryCard
                        label={category.categoryName}
                        imageSrc={category.image}
                        active={active}
                        className="w-full gap-3 [&>div]:h-[72px] [&>div]:w-[72px] [&>div]:rounded-full [&>p]:w-full [&>p]:text-[14px] [&>p]:leading-[1.35] [&>p]:font-medium [&>p]:text-text-warm-400"
                      />
                    </button>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="rounded-[24px] bg-white/70 px-4 py-8 text-center text-sm text-text-warm-100">
              표시할 카테고리가 없어요.
            </div>
          )}
        </div>
      </div>
    </BottomSheet>
  )
}

export type { CategoryBottomSheetProps }
