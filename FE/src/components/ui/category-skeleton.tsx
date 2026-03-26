interface CategorySkeletonProps {
  count?: number
}

export function CategorySkeleton({ count = 6 }: CategorySkeletonProps) {
  return (
    <>
      {Array.from(
        { length: count },
        (_, index) => `category-skeleton-${index + 1}`,
      ).map((key) => (
        <div
          key={key}
          className="flex w-[44px] shrink-0 flex-col items-center gap-2"
        >
          <div className="h-[44px] w-[44px] rounded-[8px] border border-transparent bg-neutral-200 animate-pulse" />
          <div className="h-3 w-8 rounded-sm bg-neutral-200 animate-pulse" />
        </div>
      ))}
    </>
  )
}
