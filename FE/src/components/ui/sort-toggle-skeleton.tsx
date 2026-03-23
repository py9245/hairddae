import { cn } from '@/lib/utils'

export function SortToggleSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('inline-flex rounded-full bg-primary-200 p-1', className)}
    >
      <div className="h-7 w-14 animate-pulse rounded-full bg-white/60" />
      <div className="h-7 w-14 animate-pulse rounded-full bg-transparent" />
    </div>
  )
}
