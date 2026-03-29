import { cn } from '@/lib/utils'

type CategoryCardProps = {
  label?: string
  imageSrc?: string
  active?: boolean
  className?: string
}

export function CategoryCard({
  label = '단발',
  imageSrc,
  active = false,
  className,
}: CategoryCardProps) {
  return (
    <div className={cn('flex w-[44px] flex-col items-center gap-2', className)}>
      <div
        className={cn(
          'relative h-[44px] w-[44px] overflow-hidden rounded-[8px] border transition',
          active ? 'border-primary-400' : 'border-transparent',
        )}
      >
        {imageSrc ? (
          <>
            <img
              src={imageSrc}
              alt=""
              aria-hidden="true"
              className="h-full w-full object-cover"
              draggable={false}
            />
            <div
              className={cn(
                'absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.1)_0%,rgba(255,181,191,0.42)_100%)]',
                active
                  ? 'bg-[linear-gradient(180deg,rgba(255,255,255,0.06)_0%,rgba(255,145,165,0.54)_100%)]'
                  : undefined,
              )}
            />
          </>
        ) : (
          <div className="h-full w-full bg-primary-200" />
        )}
      </div>
      <p className="w-[44px] break-all text-center text-[12px] leading-[1.2] text-text-warm-200">
        {label}
      </p>
    </div>
  )
}

export type { CategoryCardProps }
