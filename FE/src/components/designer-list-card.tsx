import { MapPin, Scissors } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { DesignerListItem } from '@/lib/Camera/designer'

type DesignerListCardProps = {
  designer: DesignerListItem
  rank: number
}

function getAvatarProfileSrc(id: DesignerListItem['id']) {
  const source = String(id)
  let sum = 0

  for (let index = 0; index < source.length; index++) {
    sum += source.charCodeAt(index)
  }

  const variant = ((sum % 5) + 1).toString().padStart(2, '0')
  return `/icon/avatar-profile-${variant}.svg`
}

export function DesignerListCard({ designer, rank }: DesignerListCardProps) {
  return (
    <article className="rounded-[28px] bg-card p-5 shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
      <div className="flex items-start gap-4">
        <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-primary-100/40">
          <img
            src={designer.profileImageUrl ?? getAvatarProfileSrc(designer.id)}
            alt={designer.name}
            className="h-full w-full object-cover"
            draggable={false}
          />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-primary-100 px-2.5 py-1 text-xs font-bold text-primary-300">
              추천 {rank}
            </span>
          </div>

          <h2 className="mt-3 truncate text-lg font-bold text-text-dark">
            {designer.name}
          </h2>

          {designer.salonName ? (
            <p className="mt-2 flex items-center gap-2 text-sm font-medium text-text-sub">
              <Scissors className="size-4 text-primary-300" />
              <span className="truncate">{designer.salonName}</span>
            </p>
          ) : null}
        </div>
      </div>

      <div className="mt-4 rounded-2xl bg-white px-4 py-3">
        <div className="flex items-start gap-2">
          <MapPin className="mt-0.5 size-4 shrink-0 text-primary-300" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-text-dark">
              {designer.name}
            </p>
            {designer.address ? (
              <p className="mt-1 text-sm leading-6 text-text-dark">
                {designer.address}
              </p>
            ) : null}
          </div>
        </div>
      </div>

      {designer.description ? (
        <p className="mt-4 text-sm leading-6 text-text-sub">
          {designer.description}
        </p>
      ) : null}

      {designer.distance ? (
        <p className="mt-4 text-right text-sm font-semibold text-text-sub">
          {designer.distance}
        </p>
      ) : null}

      <Button type="button" variant="login" size="full" className="mt-4">
        디자인 요청하기
      </Button>
    </article>
  )
}
