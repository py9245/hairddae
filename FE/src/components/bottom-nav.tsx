import { Link, useRouterState } from '@tanstack/react-router'
import type { LucideIcon } from 'lucide-react'
import { Camera, House, MessageCircle, UserRound } from 'lucide-react'

import { cn } from '@/lib/utils'

type BottomNavRoute = '/main' | '/camera' | '/chat' | '/mypage'

type BottomNavItem = {
  label: string
  to: BottomNavRoute
  icon: LucideIcon
  match: (pathname: string) => boolean
}

type BottomNavBaseProps = {
  pathname?: string
  search?: string
  interactive?: boolean
  onNavigate?: (to: BottomNavRoute) => void
}

const items: BottomNavItem[] = [
  {
    label: '홈',
    to: '/main',
    icon: House,
    match: (pathname) => pathname.startsWith('/main'),
  },
  {
    label: '카메라',
    to: '/camera',
    icon: Camera,
    match: (pathname) => pathname.startsWith('/camera'),
  },
  {
    label: '채팅',
    to: '/chat',
    icon: MessageCircle,
    match: (pathname) => pathname.startsWith('/chat'),
  },
  {
    label: '내정보',
    to: '/mypage',
    icon: UserRound,
    match: (pathname) =>
      pathname.startsWith('/mypage') || pathname.startsWith('/designer-list'),
  },
]

function shouldHideBottomNav(pathname: string, search: string) {
  if (pathname.startsWith('/chat') && search.includes('roomId=')) {
    return true
  }

  return (
    !pathname.startsWith('/main') &&
    !pathname.startsWith('/chat') &&
    !pathname.startsWith('/mypage') &&
    !pathname.startsWith('/designer-list')
  )
}

function BottomNavLink({
  label,
  to,
  isActive,
  interactive,
  onNavigate,
  icon: Icon,
}: {
  label: string
  to: BottomNavRoute
  isActive: boolean
  interactive: boolean
  onNavigate?: (to: BottomNavRoute) => void
  icon: LucideIcon
}) {
  const className = cn(
    'flex cursor-pointer flex-col items-center justify-center gap-[3px] text-center leading-[normal] not-italic transition-colors duration-200',
    isActive ? 'text-primary-250' : 'text-nav-inactive hover:text-primary-250',
  )

  const content = (
    <>
      <Icon className="size-[28px]" strokeWidth={1.5} />
      <span className="text-[12px] font-normal whitespace-nowrap">{label}</span>
    </>
  )

  if (onNavigate) {
    return (
      <button
        type="button"
        className={className}
        onClick={() => onNavigate(to)}
        aria-current={isActive ? 'page' : undefined}
      >
        {content}
      </button>
    )
  }

  if (!interactive) {
    return (
      <button
        type="button"
        className={className}
        aria-current={isActive ? 'page' : undefined}
      >
        {content}
      </button>
    )
  }

  return (
    <Link
      to={to}
      className={className}
      aria-current={isActive ? 'page' : undefined}
    >
      {content}
    </Link>
  )
}

export function BottomNavBase({
  pathname,
  search = '',
  interactive = true,
  onNavigate,
}: BottomNavBaseProps) {
  const currentPathname = pathname ?? '/'

  if (shouldHideBottomNav(currentPathname, search)) {
    return null
  }

  return (
    <nav
      aria-label="Primary"
      className="absolute right-0 bottom-0 left-0 z-10 h-[62px] rounded-t-[16px] border border-nav-inactive bg-white px-10 py-4"
    >
      <ul className="flex h-full items-center justify-between">
        {items.map(({ label, to, icon: Icon, match }) => {
          const isActive = match(currentPathname)

          return (
            <li key={to}>
              <BottomNavLink
                icon={Icon}
                interactive={interactive}
                isActive={isActive}
                label={label}
                onNavigate={onNavigate}
                to={to}
              />
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

export function BottomNav() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const search = useRouterState({
    select: (state) => state.location.searchStr,
  })

  return <BottomNavBase pathname={pathname} search={search} />
}
