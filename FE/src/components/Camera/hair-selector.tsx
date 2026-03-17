import { Download } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { HairSelectorItem } from '@/components/ui/hair-selector-item'
import type { HairItem } from '@/lib/Camera/HairItem'

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

type HairSelectorProps = {
  items: HairItem[]
  selectedId: number
  loading?: boolean
  frozen?: boolean
  onSelect: (id: number) => void
  onCapture?: () => void
  onFreezeChange?: (frozen: boolean) => void
}

type SkeletonItemProps = {
  selected?: boolean
}

function HairSelectorSkeletonItem({ selected = false }: SkeletonItemProps) {
  return (
    <div className="flex w-24 shrink-0 flex-col items-center justify-start">
      <div
        className={[
          'animate-pulse rounded-full border bg-white/20',
          selected
            ? 'h-24 w-24 border-white/35 shadow-[0_0_0_6px_rgba(255,255,255,0.10)]'
            : 'mt-3 h-16 w-16 border-white/20 opacity-80',
        ].join(' ')}
      />
    </div>
  )
}

export function HairSelector({
  items,
  selectedId,
  loading = false,
  frozen = false,
  onSelect,
  onCapture,
  onFreezeChange,
}: HairSelectorProps) {
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const [viewportWidth, setViewportWidth] = useState(0)

  const pointerStartXRef = useRef<number | null>(null)
  const pointerCurrentXRef = useRef<number | null>(null)
  const isDraggingRef = useRef(false)

  const selectedIndex = useMemo(
    () => items.findIndex((item) => item.id === selectedId),
    [items, selectedId],
  )

  useEffect(() => {
    const update = () => {
      if (viewportRef.current) {
        setViewportWidth(viewportRef.current.clientWidth)
      }
    }

    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  const SLOT_WIDTH = 96
  const swipeThreshold = 40
  const showSkeleton = loading || items.length === 0

  const translateX =
    viewportWidth > 0
      ? viewportWidth / 2 - (selectedIndex * SLOT_WIDTH + SLOT_WIDTH / 2)
      : 0

  const moveByOne = (direction: -1 | 1) => {
    if (showSkeleton || selectedIndex < 0 || frozen) return

    const nextIndex = clamp(selectedIndex + direction, 0, items.length - 1)

    if (nextIndex !== selectedIndex) {
      onSelect(items[nextIndex].id)
    }
  }

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (showSkeleton || frozen) return

    pointerStartXRef.current = e.clientX
    pointerCurrentXRef.current = e.clientX
    isDraggingRef.current = false
  }

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (showSkeleton || frozen) return
    if (pointerStartXRef.current == null) return

    pointerCurrentXRef.current = e.clientX

    const deltaX = e.clientX - pointerStartXRef.current
    if (Math.abs(deltaX) > 8) {
      isDraggingRef.current = true
    }
  }

  const handlePointerEnd = () => {
    if (showSkeleton || frozen) return

    const startX = pointerStartXRef.current
    const endX = pointerCurrentXRef.current

    pointerStartXRef.current = null
    pointerCurrentXRef.current = null

    if (startX == null || endX == null) {
      isDraggingRef.current = false
      return
    }

    const deltaX = endX - startX

    if (Math.abs(deltaX) >= swipeThreshold) {
      if (deltaX < 0) {
        moveByOne(1)
      } else {
        moveByOne(-1)
      }
    }

    window.setTimeout(() => {
      isDraggingRef.current = false
    }, 0)
  }

  function handleItemClick(itemId: number) {
    if (showSkeleton) return
    if (isDraggingRef.current) return
    if (frozen) return

    if (itemId !== selectedId) {
      onSelect(itemId)
      return
    }

    onFreezeChange?.(true)
  }

  function handleDownloadClick() {
    onCapture?.()
    onFreezeChange?.(false)
  }

  return (
    <div className="absolute bottom-0 left-0 right-0 z-30">
      <div className="bg-gradient-to-t from-black/80 via-black/45 to-transparent px-4 pb-6 pt-16">
        <div
          ref={viewportRef}
          className="relative touch-pan-y select-none"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onPointerCancel={handlePointerEnd}
          onPointerLeave={handlePointerEnd}
        >
          <div className="pointer-events-none absolute inset-y-0 left-1/2 z-10 w-24 -translate-x-1/2 rounded-full border border-white/30" />

          {frozen ? (
            <div className="flex items-center justify-center">
              <button
                type="button"
                onClick={handleDownloadClick}
                aria-label="캡처 다운로드"
                className="flex items-center justify-center"
              >
                <div className="relative flex h-24 w-24 items-center justify-center overflow-hidden rounded-full border border-white bg-white shadow-[0_0_0_6px_rgba(255,255,255,0.25)] transition-all duration-300">
                  <Download className="h-10 w-10 text-slate-700" />
                </div>
              </button>
            </div>
          ) : showSkeleton ? (
            <div className="flex items-start justify-center">
              <HairSelectorSkeletonItem />
              <HairSelectorSkeletonItem />
              <HairSelectorSkeletonItem selected />
              <HairSelectorSkeletonItem />
              <HairSelectorSkeletonItem />
            </div>
          ) : (
            <div
              className="flex items-center transition-transform duration-300 ease-out"
              style={{ transform: `translateX(${translateX}px)` }}
            >
              {items.map((item) => {
                const selected = item.id === selectedId

                return (
                  <HairSelectorItem
                    key={item.id}
                    item={item}
                    selected={selected}
                    onClick={() => handleItemClick(item.id)}
                  />
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
