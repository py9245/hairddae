import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type RouteCardProps = {
  eyebrow: string
  title: string
  description: string
  children?: ReactNode
  className?: string
}

export function RouteCard({
  eyebrow,
  title,
  description,
  children,
  className,
}: RouteCardProps) {
  return (
    <section
      className={cn(
        'w-full rounded-[2rem] border border-white/40 bg-white/85 p-8 shadow-[0_24px_80px_rgba(15,23,42,0.15)] backdrop-blur',
        className,
      )}
    >
      <p className="text-xs font-semibold uppercase tracking-[0.35em] text-sky-700">
        {eyebrow}
      </p>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950">
        {title}
      </h1>
      <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600">
        {description}
      </p>
      {children && <div className="mt-8">{children}</div>}
    </section>
  )
}
