import { cn } from '@/lib/utils'

type CategoryCardProps = {
  label?: string
  className?: string
}

export function CategoryCard({ label = '단발', className }: CategoryCardProps) {
  return (
    <div className={cn('flex flex-col items-center', className)}>
      <div className="h-[44px] w-[44px] rounded-[8px] bg-primary-200" />
      <p className="w-[44px] break-all text-center text-[16px] leading-[1.4] text-[#502D2D]">
        {label}
      </p>
    </div>
  )
}

export type { CategoryCardProps }
