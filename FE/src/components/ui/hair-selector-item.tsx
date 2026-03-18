import clsx from 'clsx'
import { Ban } from 'lucide-react'
import type { HairItem } from '@/lib/Camera/HairItem'

type HairSelectorItemProps = {
  item: HairItem
  selected: boolean
  onClick: () => void
  disabled?: boolean
}

export function HairSelectorItem({
  item,
  selected,
  onClick,
  disabled = false,
}: HairSelectorItemProps) {
  const isEmpty = item.id === 0

  return (
    <div className="flex w-24 shrink-0 justify-center">
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-label={item.label}
        className={clsx(
          'flex items-center justify-center transition-opacity',
          disabled && 'cursor-not-allowed opacity-50',
        )}
      >
        <div
          className={clsx(
            'relative flex items-center justify-center overflow-hidden rounded-full border bg-white transition-all duration-300',
            selected
              ? 'h-24 w-24 border-white shadow-[0_0_0_6px_rgba(255,255,255,0.25)]'
              : 'h-16 w-16 border-white/40 opacity-85',
          )}
        >
          {isEmpty ? (
            selected ? null : (
              <Ban className="h-12 w-12 text-slate-500 opacity-80 transition-all duration-300" />
            )
          ) : (
            <img
              src={item.thumb}
              alt={item.label}
              className={clsx(
                'select-none object-contain transition-all duration-300',
                selected ? 'h-20 w-20 opacity-100' : 'h-12 w-12 opacity-80',
              )}
              draggable={false}
            />
          )}
        </div>
      </button>
    </div>
  )
}
