import { cn } from '@/lib/utils'

interface HairStyleSkeletonProps {
  count?: number
  className?: string
}

export function HairStyleSkeleton({
  count = 4,
  className,
}: HairStyleSkeletonProps) {
  return (
    <div className={cn('grid grid-cols-2 gap-x-3 gap-y-4', className)}>
      {Array.from(
        { length: count },
        (_, index) => `hair-style-skeleton-${index + 1}`,
      ).map((key) => (
        <div
          key={key}
          className="h-[240px] w-full rounded-xl bg-neutral-200 animate-pulse"
        />
      ))}
    </div>
  )
}
