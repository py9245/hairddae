import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type HeaderProps = {
  label?: string
  labelClassName?: string
  leftAction?: ReactNode
  centerContent?: ReactNode
  rightAction?: ReactNode
  className?: string
}

export function Header({
  label,
  labelClassName,
  leftAction,
  centerContent,
  rightAction,
  className,
}: HeaderProps) {
  if (label !== undefined) {
    return (
      <div className={cn('flex items-end gap-3 px-4 py-3', className)}>
        <img src="/icon/logo.svg" alt={`${label} 로고`} className="size-12" />
        <span className={cn('font-display text-[32px] font-bold leading-none', labelClassName)}>
          {label}
        </span>
      </div>
    )
  }

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
