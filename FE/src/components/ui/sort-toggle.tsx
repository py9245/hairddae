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
    <div className={cn('inline-flex rounded-full bg-[#f18b90] p-1', className)}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cn(
            'rounded-full px-4 py-1 text-sm font-medium transition-colors',
            option.value === value
              ? 'bg-white text-[#ea7589]'
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
