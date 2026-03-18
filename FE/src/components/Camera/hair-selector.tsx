import { Download } from 'lucide-react'
import { HairSelectorItem } from '@/components/ui/hair-selector-item'
import { useHairSelectorController } from '@/hooks/Camera/useHairSelectorController'
import type { HairItem } from '@/lib/Camera/HairItem'

type HairSelectorProps = {
  items: HairItem[]
  selectedId: number
  loading?: boolean
  frozen?: boolean
  onSelect: (id: number) => void
  onCapture?: () => void
  onFreezeChange?: (frozen: boolean) => void
}

function HairSelectorSkeletonItem({ selected = false }: { selected?: boolean }) {
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

export function HairSelector(props: HairSelectorProps) {
  const {
    viewportRef,
    showSkeleton,
    translateX,
    handlePointerDown,
    handlePointerMove,
    handlePointerEnd,
    handleItemClick,
    handleDownloadClick,
  } = useHairSelectorController(props)

  const { items, selectedId, frozen = false } = props

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
              {items.map((item) => (
                <HairSelectorItem
                  key={item.id}
                  item={item}
                  selected={item.id === selectedId}
                  onClick={() => handleItemClick(item.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}