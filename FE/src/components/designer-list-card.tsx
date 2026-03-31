import { MapPin } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { DesignerListItem } from '@/lib/Camera/designer'

type DesignerListCardProps = {
  designer: DesignerListItem
  rank: number
  requestPending?: boolean
  onRequest?: (designer: DesignerListItem) => void
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

export function DesignerListCard({
  designer,
  rank,
  requestPending = false,
  onRequest,
}: DesignerListCardProps) {
  return (
    <article className="rounded-[28px] bg-card p-5 shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
      <div className="flex items-start gap-4">
        <div className="flex h-32 w-[44%] shrink-0 items-center justify-center overflow-hidden rounded-[24px] bg-primary-100/40">
          <img
            src={designer.profileImageUrl ?? getAvatarProfileSrc(designer.id)}
            alt={designer.name}
            className="h-full w-full object-cover"
            draggable={false}
          />
        </div>

        <div className="flex h-32 min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2">
            <span className="shrink-0 rounded-full bg-primary-100 px-2.5 py-1 text-xs font-bold text-primary-300">
              추천 {rank}
            </span>
            <h2 className="min-w-0 truncate text-lg font-bold text-text-dark">
              {designer.name}
            </h2>
          </div>

          {designer.address ? (
            <div className="mt-2 flex items-start gap-2">
              <MapPin className="mt-0.5 size-4 shrink-0 text-primary-300" />
              <p className="line-clamp-2 text-sm leading-5 text-text-dark">
                {designer.address}
              </p>
            </div>
          ) : null}

          <Button
            type="button"
            variant="login"
            className="mt-auto h-10 rounded-xl text-sm"
            onClick={() => onRequest?.(designer)}
            disabled={requestPending}
          >
            {requestPending ? '요청 중...' : '디자인 요청하기'}
          </Button>
        </div>
      </div>
    </article>
  )
}
