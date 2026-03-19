import { cn } from '@/lib/utils'

type HairStyleCardProps = {
  imageSrc: string
  imageAlt: string
  title: string
  subtitle: string
  priority?: boolean
  liked?: boolean
  className?: string
  onLikeToggle?: () => void
  onApply?: () => void
}

export function HairStyleCard({
  imageSrc,
  imageAlt,
  title,
  subtitle,
  priority = false,
  liked = false,
  className,
  onLikeToggle,
  onApply,
}: HairStyleCardProps) {
  const heartIconSrc = liked ? '/icon/heart-fill.svg' : '/icon/hair-empty.svg'
  const heartLabel = liked ? '찜 해제' : '찜하기'

  return (
    <article
      className={cn(
        'relative isolate w-[170px] overflow-hidden rounded-[8px] bg-[#ea7589]',
        className,
      )}
    >
      <div className="relative w-[170px]">
        <img
          src={imageSrc}
          alt={imageAlt}
          width={166}
          loading={priority ? 'eager' : 'lazy'}
          decoding="async"
          fetchPriority={priority ? 'high' : 'auto'}
          className="mx-[2px] mt-[2px] block w-[166px] rounded-[8px] object-cover object-center"
          draggable={false}
        />

        <div className="absolute inset-x-0 bottom-0 rounded-b-[8px] bg-[linear-gradient(180deg,rgba(255,162,159,0)_0%,rgba(255,162,159,0.45)_28%,rgba(255,167,165,0.78)_62%,#FFAEAC_100%)] px-[10px] pb-[10px] pt-[12px]">
          <div className="flex flex-col gap-[8px]">
            <div className="flex w-[150px] flex-col items-start text-white">
              <h3 className="w-[140px] whitespace-pre-line text-[17px] leading-[1.15] font-semibold tracking-[-0.02em]">
                {title}
              </h3>
              <p className="mt-[3px] self-stretch text-[11px] leading-[1.2] font-normal text-[#f8f8f8]">
                {subtitle}
              </p>
            </div>

            <div className="pointer-events-auto flex w-[150px] items-center justify-between">
              <button
                type="button"
                aria-label="적용하기"
                className="rounded-full bg-primary-300 px-[18px] py-[6px] text-[14px] leading-none font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent"
                onClick={onApply}
              >
                적용하기
              </button>
              <button
                type="button"
                aria-label={heartLabel}
                aria-pressed={liked}
                className="relative z-30 flex size-[18px] shrink-0 items-center justify-center rounded-full bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent"
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
        </div>
      </div>
    </article>
  )
}
