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
      <div className="relative h-[200px] w-[170px]">
        <img
          src={imageSrc}
          alt={imageAlt}
          width={166}
          height={196}
          loading={priority ? 'eager' : 'lazy'}
          decoding="async"
          fetchPriority={priority ? 'high' : 'auto'}
          className="absolute left-[2px] top-[2px] h-[196px] w-[166px] rounded-[8px] object-cover object-center"
          draggable={false}
        />

        <div className="absolute left-0 top-[133px] flex h-[67px] w-[170px] flex-col gap-[10px] rounded-b-[8px] bg-[linear-gradient(180deg,rgba(255,162,159,0)_0%,rgba(255,162,159,0.4)_31%,rgba(255,167,165,0.7)_64%,#FFAEAC_100%)] px-[8px] py-[8px]">
          <div className="flex w-[154px] items-end justify-between">
            <div className="flex w-[73px] flex-col items-start text-white">
              <h3 className="w-[77px] whitespace-pre-line text-[16px] leading-[1.18] font-normal tracking-[-0.02em]">
                {title}
              </h3>
              <p className="mt-[2px] self-stretch text-[10px] leading-[1.2] font-normal text-[#f8f8f8]">
                {subtitle}
              </p>
            </div>

            <button
              type="button"
              aria-label={heartLabel}
              aria-pressed={liked}
              className="flex size-[18px] shrink-0 items-center justify-center rounded-full bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent"
              onClick={onLikeToggle}
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
    </article>
  )
}
