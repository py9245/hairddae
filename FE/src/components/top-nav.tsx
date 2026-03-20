import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type TopNavProps = {
  leftAction?: ReactNode
  centerContent?: ReactNode
  rightAction?: ReactNode
  className?: string
}

export function TopNav({
  leftAction,
  centerContent,
  rightAction,
  className,
}: TopNavProps) {
  return (
    <div className={cn('absolute inset-x-0 top-0 z-20 px-4 pt-5', className)}>
      <div className="grid grid-cols-[48px_1fr_48px] items-center gap-3">
        <div className="flex items-center justify-start">{leftAction}</div>
        <div className="flex items-center justify-center text-center">
          {centerContent}
        </div>
        <div className="flex items-center justify-end">{rightAction}</div>
      </div>
    </div>
  )
}
