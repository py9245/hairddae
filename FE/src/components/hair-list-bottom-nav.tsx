import { Link } from '@tanstack/react-router'
import type { LucideIcon } from 'lucide-react'
import { Camera, ChevronLeft, MessageCircle, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'

import { cn } from '@/lib/utils'

type HairListBottomNavRoute = '/camera' | '/chat' | '/mypage'

type HairListBottomNavProps = {
  interactive?: boolean
  isExiting?: boolean
  onBack?: () => void
  onNavigate?: (to: HairListBottomNavRoute) => void
  className?: string
}

type HairListBottomNavItem = {
  label: string
  to: HairListBottomNavRoute
  icon: LucideIcon
}

const items: HairListBottomNavItem[] = [
  {
    label: '카메라',
    to: '/camera',
    icon: Camera,
  },
  {
    label: '채팅',
    to: '/chat',
    icon: MessageCircle,
  },
  {
    label: '내정보',
    to: '/mypage',
    icon: UserRound,
  },
]

function MenuItem({
  label,
  to,
  icon: Icon,
  interactive,
  onNavigate,
}: HairListBottomNavItem & {
  interactive: boolean
  onNavigate?: (to: HairListBottomNavRoute) => void
}) {
  const className = cn(
    'flex cursor-pointer flex-col items-center justify-center gap-[3px] text-center leading-[normal] not-italic text-nav-inactive transition-colors duration-200 hover:text-primary-250',
  )

  const content = (
    <>
      <Icon className="size-[26px]" strokeWidth={1.75} />
      <span className="text-[12px] font-normal whitespace-nowrap">{label}</span>
    </>
  )

  if (onNavigate) {
    return (
      <button
        type="button"
        className={className}
        onClick={() => onNavigate(to)}
      >
        {content}
      </button>
    )
  }

  if (!interactive) {
    return (
      <button type="button" className={className}>
        {content}
      </button>
    )
  }

  return (
    <Link to={to} className={className}>
      {content}
    </Link>
  )
}

export function HairListBottomNav({
  interactive = true,
  isExiting = false,
  onBack,
  onNavigate,
  className,
}: HairListBottomNavProps) {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    let innerFrameId = 0
    const frameId = window.requestAnimationFrame(() => {
      innerFrameId = window.requestAnimationFrame(() => {
        setIsVisible(true)
      })
    })

    return () => {
      window.cancelAnimationFrame(frameId)
      if (innerFrameId) {
        window.cancelAnimationFrame(innerFrameId)
      }
    }
  }, [])

  return (
    <nav
      aria-label="Hair list navigation"
      className={cn(
        'absolute inset-x-0 bottom-0 z-20 mx-auto w-full max-w-[390px] px-4 pb-4',
        className,
      )}
    >
      <div
        className={cn(
          'grid grid-cols-4 items-center rounded-[28px] border border-white/70 bg-white/95 px-4 py-2 shadow-[0_20px_44px_rgba(15,23,42,0.16)] backdrop-blur-sm will-change-transform',
          isExiting
            ? 'animate-hair-list-bottom-nav-out'
            : isVisible
              ? 'animate-hair-list-bottom-nav-in'
              : 'translate-y-6 scale-[0.985] opacity-0',
        )}
      >
        <div className="flex items-center justify-center">
          {onBack ? (
            <button
              type="button"
              disabled={isExiting}
              onClick={onBack}
              aria-label="메인으로 이동"
              className="inline-flex size-11 items-center justify-center rounded-full bg-neutral-100 text-text-warm-500 transition-colors hover:bg-neutral-200 disabled:pointer-events-none"
            >
              <ChevronLeft className="size-6" strokeWidth={2} />
            </button>
          ) : interactive ? (
            <Link
              to="/main"
              aria-label="메인으로 이동"
              className={cn(
                'inline-flex size-11 items-center justify-center rounded-full bg-neutral-100 text-text-warm-500 transition-colors hover:bg-neutral-200',
                isExiting && 'pointer-events-none',
              )}
            >
              <ChevronLeft className="size-6" strokeWidth={2} />
            </Link>
          ) : (
            <button
              type="button"
              aria-label="메인으로 이동"
              className="inline-flex size-11 items-center justify-center rounded-full bg-neutral-100 text-text-warm-500"
            >
              <ChevronLeft className="size-6" strokeWidth={2} />
            </button>
          )}
        </div>

        {items.map((item) => (
          <div key={item.to} className="flex items-center justify-center">
            <MenuItem
              {...item}
              interactive={interactive}
              onNavigate={onNavigate}
            />
          </div>
        ))}
      </div>
    </nav>
  )
}

export type { HairListBottomNavProps, HairListBottomNavRoute }
