interface HairStyleSkeletonProps {
  count?: number
}

export function HairStyleSkeleton({ count = 4 }: HairStyleSkeletonProps) {
  return (
    <div className="grid grid-cols-2 gap-x-3 gap-y-4">
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
