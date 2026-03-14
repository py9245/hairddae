import clsx from 'clsx'
import { Download } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

type HairItem = {
  id: number
  img: string
  thumb: string
  label: string
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

export function HairSelector({
  items,
  selectedId,
  onSelect,
}: {
  items: HairItem[]
  selectedId: number
  onSelect: (id: number) => void
}) {
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const [viewportWidth, setViewportWidth] = useState(0)

  const touchStartXRef = useRef<number | null>(null)
  const touchEndXRef = useRef<number | null>(null)

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

  const translateX =
    viewportWidth > 0
      ? viewportWidth / 2 - (selectedIndex * SLOT_WIDTH + SLOT_WIDTH / 2)
      : 0

  const moveByOne = (direction: -1 | 1) => {
    if (selectedIndex < 0) return

    const nextIndex = clamp(selectedIndex + direction, 0, items.length - 1)

    if (nextIndex !== selectedIndex) {
      onSelect(items[nextIndex].id)
    }
  }

  return (
    <div className="absolute bottom-0 left-0 right-0 z-30">
      <div className="bg-gradient-to-t from-black/80 via-black/45 to-transparent px-4 pb-6 pt-16">
        <div
          ref={viewportRef}
          className="relative overflow-hidden"
          onTouchStart={(e) => {
            touchStartXRef.current = e.touches[0].clientX
            touchEndXRef.current = null
          }}
          onTouchMove={(e) => {
            touchEndXRef.current = e.touches[0].clientX
          }}
          onTouchEnd={() => {
            const startX = touchStartXRef.current
            const endX = touchEndXRef.current

            if (startX == null || endX == null) return

            const deltaX = endX - startX
            if (Math.abs(deltaX) < swipeThreshold) return

            if (deltaX < 0) {
              moveByOne(1)
            } else {
              moveByOne(-1)
            }
          }}
        >
          <div className="pointer-events-none absolute inset-y-0 left-1/2 z-10 w-24 -translate-x-1/2 rounded-full border border-white/30" />

          <div
            className="flex items-center transition-transform duration-300 ease-out"
            style={{
              transform: `translateX(${translateX}px)`,
            }}
          >
            {items.map((item) => {
              const selected = item.id === selectedId
              const isEmpty = item.id === 0

              return (
                <div
                  key={item.id}
                  className="flex w-24 shrink-0 justify-center"
                >
                  <button
                    type="button"
                    onClick={() => onSelect(item.id)}
                    aria-label={item.label}
                    className="flex items-center justify-center"
                  >
                    <div
                      className={clsx(
                        'relative flex items-center justify-center overflow-hidden rounded-full border bg-white transition-all duration-300',
                        selected
                          ? 'h-24 w-24 border-white shadow-[0_0_0_6px_rgba(255,255,255,0.25)]'
                          : 'h-16 w-16 border-white/40 opacity-85',
                      )}
                    >
                      {!isEmpty && (
                        <img
                          src={item.thumb}
                          alt={item.label}
                          className={clsx(
                            'select-none object-contain transition-all duration-300',
                            selected
                              ? 'h-20 w-20 opacity-40'
                              : 'h-12 w-12 opacity-80',
                          )}
                          draggable={false}
                        />
                      )}

                      {selected && (
                        <Download className="absolute h-12 w-12 text-slate-700" />
                      )}
                    </div>
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
