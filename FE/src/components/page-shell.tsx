import type { CSSProperties, ReactNode } from 'react'

import { cn } from '@/lib/utils'

type PageShellProps = {
  accent: string
  badge: string
  title: string
  description: string
  children?: ReactNode
  action?: ReactNode
  className?: string
}

export function PageShell({
  accent,
  badge,
  title,
  description,
  children,
  action,
  className,
}: PageShellProps) {
  return (
    <main
      className={cn(
        'app-frame-page bg-[radial-gradient(circle_at_top_left,white,transparent_38%),linear-gradient(135deg,var(--page-accent)_0%,#0f172a_82%)] px-6 py-10 text-white',
        className,
      )}
      style={{ '--page-accent': accent } as CSSProperties}
    >
      <div className="app-frame-fill mx-auto flex max-w-5xl flex-col rounded-[2rem] border border-white/20 bg-white/10 p-8 shadow-[0_24px_100px_rgba(15,23,42,0.28)] backdrop-blur md:p-10">
        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-white/70">
              {badge}
            </p>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight">
              {title}
            </h1>
            <p className="mt-4 text-sm leading-6 text-white/75">
              {description}
            </p>
          </div>
          {action}
        </div>
        {children && <div className="mt-10 flex-1">{children}</div>}
      </div>
    </main>
  )
}
