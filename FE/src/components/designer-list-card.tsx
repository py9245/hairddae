import { MapPin, Scissors, UserRound } from 'lucide-react'

import type { DesignerListItem } from '@/lib/Camera/designer'

type DesignerListCardProps = {
  designer: DesignerListItem
  rank: number
}

export function DesignerListCard({ designer, rank }: DesignerListCardProps) {
  return (
    <article className="rounded-[28px] bg-card p-5 shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
      <div className="flex items-start gap-4">
        <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-primary-100/40">
          {designer.profileImageUrl ? (
            <img
              src={designer.profileImageUrl}
              alt={designer.name}
              className="h-full w-full object-cover"
            />
          ) : (
            <UserRound className="size-7 text-primary-300" />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-primary-100 px-2.5 py-1 text-xs font-bold text-primary-300">
              추천 {rank}
            </span>
            {designer.distance ? (
              <span className="text-xs font-medium text-text-sub">
                {designer.distance}
              </span>
            ) : null}
          </div>

          <div className="mt-3">
            <h2 className="truncate text-lg font-bold text-text-dark">
              {designer.name}
            </h2>
            {designer.salonName ? (
              <p className="mt-1 flex items-center gap-2 text-sm font-medium text-text-sub">
                <Scissors className="size-4 text-primary-300" />
                <span className="truncate">{designer.salonName}</span>
              </p>
            ) : null}
          </div>
        </div>
      </div>

      {designer.address ? (
        <div className="mt-4 flex items-start gap-2 rounded-2xl bg-white px-4 py-3">
          <MapPin className="mt-0.5 size-4 shrink-0 text-primary-300" />
          <p className="text-sm leading-6 text-text-dark">{designer.address}</p>
        </div>
      ) : null}

      {designer.description ? (
        <p className="mt-4 text-sm leading-6 text-text-sub">
          {designer.description}
        </p>
      ) : null}
    </article>
  )
}
