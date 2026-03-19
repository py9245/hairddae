import { cn } from '@/lib/utils'

export function StyleAdsCardSkeleton({ className }: { className?: string }) {
  return (
    <article
      className={cn(
        'relative isolate w-[360px] overflow-hidden rounded-lg bg-white shadow-[0_0.4px_4px_1px_rgba(0,0,0,0.25)]',
        className,
      )}
    >
      <div className="h-[320px] w-full animate-pulse bg-gray-200" />
      <div className="absolute bottom-0 left-0 right-0 rounded-b-lg bg-gradient-to-t from-white/95 via-white/70 to-transparent px-3 pb-3 pt-10">
        <div className="flex items-start justify-between">
          <div className="min-w-0 flex-1">
            <div className="h-4 w-3/5 animate-pulse rounded bg-gray-300" />
            <div className="mt-1.5 h-3 w-2/5 animate-pulse rounded bg-gray-200" />
          </div>
          <div className="ml-2 size-[18px] shrink-0 animate-pulse rounded-full bg-gray-300" />
        </div>
      </div>
    </article>
  )
}

type StyleAdsCardProps = {
  hairImgpath: string
  hairName: string
  hairSlug?: string
  liked?: boolean
  priority?: boolean
  className?: string
  onLikeToggle?: () => void
  onApply?: () => void
}

export function StyleAdsCard({
  hairImgpath,
  hairName,
  hairSlug,
  liked = false,
  priority = false,
  className,
  onLikeToggle,
  onApply,
}: StyleAdsCardProps) {
  const heartIconSrc = liked ? '/icon/heart-fill.svg' : '/icon/hair-empty.svg'
  const heartLabel = liked ? '찜 해제' : '찜하기'

  return (
    <article
      className={cn(
        'relative isolate w-[360px] overflow-hidden rounded-lg bg-white shadow-[0_0.4px_4px_1px_rgba(0,0,0,0.25)]',
        className,
      )}
    >
      <img
        src={hairImgpath}
        alt={hairName}
        width={360}
        height={320}
        loading={priority ? 'eager' : 'lazy'}
        decoding="async"
        fetchPriority={priority ? 'high' : 'auto'}
        className="h-[320px] w-full object-cover object-center"
        draggable={false}
      />
      <div className="absolute bottom-0 left-0 right-0 rounded-b-lg bg-gradient-to-t from-white/95 via-white/70 to-transparent px-3 pb-3 pt-10">
        <div className="flex items-end justify-between">
          <div className="min-w-0">
            <h3 className="line-clamp-2 text-xl font-extrabold leading-snug text-neutral-800">
              {hairSlug}
            </h3>
            {hairName && (
              <p className="mt-0.5 text-sm text-labels-secondary">{hairName}</p>
            )}
          </div>
        </div>
        <div className="mt-3 flex items-center justify-between">
          <button
            type="button"
            aria-label="적용하기"
            className="rounded-full bg-primary-300 px-5 py-2 text-sm font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 focus-visible:ring-offset-2"
            onClick={onApply}
          >
            적용하기
          </button>
          <button
            type="button"
            aria-label={heartLabel}
            aria-pressed={liked}
            className="relative z-30 ml-2 flex size-[18px] shrink-0 items-center justify-center rounded-full bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 focus-visible:ring-offset-2"
            onClick={(event) => {
              event.stopPropagation()
              onLikeToggle?.()
            }}
          >
            <img
              src={heartIconSrc}
              alt=""
              aria-hidden="true"
              className="size-[18px] object-contain"
            />
          </button>
        </div>
      </div>
    </article>
  )
}
