import { useEffect, useMemo, useRef, useState } from 'react'
import type { HairItem } from '@/lib/Camera/HairItem'

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

type Args = {
  items: HairItem[]
  selectedId: number
  loading?: boolean
  frozen?: boolean
  onSelect: (id: number) => void
  onCapture?: () => void
  onFreezeChange?: (frozen: boolean) => void
}

export function useHairSelectorController({
  items,
  selectedId,
  loading = false,
  frozen = false,
  onSelect,
  onCapture,
  onFreezeChange,
}: Args) {
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const [viewportWidth, setViewportWidth] = useState(0)

  const pointerStartXRef = useRef<number | null>(null)
  const pointerCurrentXRef = useRef<number | null>(null)
  const isDraggingRef = useRef(false)

  const SLOT_WIDTH = 96
  const swipeThreshold = 40
  const showSkeleton = loading || items.length === 0

  const selectedIndex = useMemo(() => {
    const matchedIndex = items.findIndex((item) => item.id === selectedId)

    if (matchedIndex >= 0) {
      return matchedIndex
    }

    // If the requested hair id is not present in the loaded list yet,
    // keep the "none" option on the left by centering the first real item.
    if (selectedId > 0 && items.length > 1) {
      return 1
    }

    return 0
  }, [items, selectedId])

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

    if (Math.abs(e.clientX - pointerStartXRef.current) > 8) {
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
      moveByOne(deltaX < 0 ? 1 : -1)
    }

    window.setTimeout(() => {
      isDraggingRef.current = false
    }, 0)
  }

  const handleItemClick = (itemId: number) => {
    if (showSkeleton || frozen || isDraggingRef.current) return

    if (itemId !== selectedId) {
      onSelect(itemId)
      return
    }

    if (onFreezeChange) {
      onFreezeChange(true)
      return
    }

    onCapture?.()
  }

  const handleDownloadClick = () => {
    onCapture?.()
  }

  return {
    viewportRef,
    showSkeleton,
    translateX,
    handlePointerDown,
    handlePointerMove,
    handlePointerEnd,
    handleItemClick,
    handleDownloadClick,
  }
}
