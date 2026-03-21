import { useState } from 'react'
import { cn } from '@/lib/utils'

type HairStyleCardProps = {
  hairId: number
  imageSrc: string
  imageAlt: string
  hairName: string
  hookText: string
  priority?: boolean
  liked?: boolean
  className?: string
  onLikeToggle?: () => void
  onApply?: (hairId: number) => void | Promise<void>
}

export function HairStyleCard({
  hairId,
  imageSrc,
  imageAlt,
  hairName,
  hookText,
  priority = false,
  liked = false,
  className,
  onLikeToggle,
  onApply,
}: HairStyleCardProps) {
  const [isApplying, setIsApplying] = useState(false)
  const heartIconSrc = liked ? '/icon/heart-fill.svg' : '/icon/hair-empty.svg'
  const heartLabel = liked ? '찜 해제' : '찜하기'

  async function handleApplyClick() {
    if (!onApply || isApplying) {
      return
    }

    setIsApplying(true)

    try {
      await onApply(hairId)
    } finally {
      setIsApplying(false)
    }
  }

  return (
    <article
      className={cn(
        'group relative isolate w-[170px] overflow-hidden rounded-[14px] bg-primary-150 p-[2px] transition-all duration-300 hover:shadow-pink-card',
        className,
      )}
    >
      <div className="relative aspect-[3/4] w-full overflow-hidden rounded-[12px]">
        <img
          src={imageSrc}
          alt={imageAlt}
          loading={priority ? 'eager' : 'lazy'}
          decoding="async"
          fetchPriority={priority ? 'high' : 'auto'}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
          draggable={false}
        />

        <div className="absolute inset-x-0 bottom-0 flex flex-col justify-end bg-gradient-to-t from-black/80 via-black/30 to-transparent p-[10px] pt-[40px]">
          <div className="flex flex-col gap-[10px]">
            <div className="flex flex-col items-start text-white">
              <p className="text-[11px] font-medium text-white/90 drop-shadow-sm">
                {hookText}
              </p>
              <h3 className="mt-[2px] w-full whitespace-pre-line text-[19px] leading-[1.2] font-bold tracking-tight drop-shadow-md">
                {hairName}
              </h3>
            </div>

            <div className="flex items-center justify-start">
              <button
                type="button"
                aria-label="적용하기"
                disabled={isApplying}
                className={cn(
                  'rounded-full bg-brand px-[16px] py-[6px] text-[13px] font-bold text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80',
                  isApplying
                    ? 'cursor-wait opacity-70'
                    : 'hover:bg-primary-hover',
                )}
                onClick={handleApplyClick}
              >
                적용하기
              </button>

              <button
                type="button"
                aria-label={heartLabel}
                aria-pressed={liked}
                className="relative z-30 ml-auto flex items-center justify-center rounded-full bg-white/10 p-1.5 backdrop-blur-md transition-all hover:bg-white/20 active:scale-90"
                onClick={(event) => {
                  event.stopPropagation()
                  onLikeToggle?.()
                }}
              >
                <img
                  src={heartIconSrc}
                  alt=""
                  aria-hidden="true"
                  className={cn(
                    'size-[16px] object-contain transition-transform',
                    liked && 'animate-heartbeat',
                  )}
                />
              </button>
            </div>
          </div>
        </div>
      </div>
    </article>
  )
}
