import { Download } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { HairSelectorItem } from '@/components/ui/hair-selector-item'
import { useHairSelectorController } from '@/hooks/Camera/useHairSelectorController'
import type { HairItem } from '@/lib/Camera/HairItem'
import { cn } from '@/lib/utils'

type HairSelectorProps = {
  items: HairItem[]
  selectedId: number
  loading?: boolean
  frozen?: boolean
  aiEnhancePending?: boolean
  onSelect: (id: number) => void
  onCapture?: () => void
  onFreezeChange?: (frozen: boolean) => void
  onFindDesigner?: () => void
  onAiEnhance?: () => void
}

function HairSelectorSkeletonItem({
  selected = false,
}: {
  selected?: boolean
}) {
  return (
    <div className="flex w-24 shrink-0 flex-col items-center justify-start">
      <div
        className={cn(
          'animate-pulse rounded-full border bg-white/20',
          selected
            ? 'h-24 w-24 border-white/35 shadow-[0_0_0_6px_rgba(255,255,255,0.10)]'
            : 'mt-3 h-16 w-16 border-white/20 opacity-80',
        )}
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

  const {
    items,
    selectedId,
    frozen = false,
    aiEnhancePending = false,
    onFindDesigner,
    onAiEnhance,
  } = props

  const overlayClassName =
    'pointer-events-none absolute inset-y-0 left-1/2 z-10 w-24 -translate-x-1/2 rounded-full border border-white/30'

  const trackClassName = cn(
    'flex transition-transform duration-300 ease-out',
    showSkeleton ? 'items-start justify-center' : 'items-center',
  )

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
          <div className={overlayClassName} />

          {frozen ? (
            <div className="flex flex-col items-center gap-3">
              <div className="flex w-full gap-2 px-4">
                <Button
                  type="button"
                  variant="login"
                  className="h-12 flex-1 rounded-xl"
                  onClick={onFindDesigner}
                  disabled={aiEnhancePending}
                >
                  디자이너 찾기
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-12 flex-1 rounded-xl bg-white text-text-dark hover:bg-neutral-100"
                  onClick={onAiEnhance}
                  disabled={aiEnhancePending}
                >
                  {aiEnhancePending ? 'AI 보정중...' : 'AI 보정하기'}
                </Button>
              </div>
              <Button
                type="button"
                variant="hair-download"
                size="camera-download"
                onClick={handleDownloadClick}
                data-testid="camera-download-button"
                aria-label="캡처 다운로드"
                disabled={aiEnhancePending}
              >
                <Download className="size-12 text-slate-700" />
              </Button>
            </div>
          ) : showSkeleton ? (
            <div className={trackClassName}>
              <HairSelectorSkeletonItem />
              <HairSelectorSkeletonItem />
              <HairSelectorSkeletonItem selected />
              <HairSelectorSkeletonItem />
              <HairSelectorSkeletonItem />
            </div>
          ) : (
            <div
              className={trackClassName}
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
