import { cn } from '@/lib/utils'

type SortOption<T extends string> = { value: T; label: string }

type SortToggleProps<T extends string> = {
  options: readonly [SortOption<T>, SortOption<T>]
  value: T
  onChange: (value: T) => void
  className?: string
}

function SortToggle<T extends string>({
  options,
  value,
  onChange,
  className,
}: SortToggleProps<T>) {
  return (
    <div
      className={cn('inline-flex rounded-full bg-primary-200 p-1', className)}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cn(
            'rounded-full px-3 py-1 text-xs font-medium transition-colors sm:px-4 sm:text-sm',
            option.value === value
              ? 'bg-white text-primary-300'
              : 'bg-transparent text-white',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export { SortToggle }
export type { SortToggleProps, SortOption }
