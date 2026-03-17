import clsx from 'clsx'
import { Ban, Download } from 'lucide-react'
import type { HairItem } from '@/lib/Camera/HairItem'

type HairSelectorItemProps = {
  item: HairItem
  selected: boolean
  onClick: () => void
}

export function HairSelectorItem({
  item,
  selected,
  onClick,
}: HairSelectorItemProps) {
  const isEmpty = item.id === 0

  return (
    <div className="flex w-24 shrink-0 justify-center">
      <button
        type="button"
        onClick={onClick}
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
          {!isEmpty && !selected && (
            <img
              src={item.thumb}
              alt={item.label}
              className="h-12 w-12 select-none object-contain opacity-80 transition-all duration-300"
              draggable={false}
            />
          )}

          {isEmpty && !selected && (
            <Ban className="h-12 w-12 text-slate-500 opacity-80" />
          )}

          {selected && (
            <Download className="absolute h-12 w-12 text-slate-700" />
          )}
        </div>
      </button>
    </div>
  )
}
