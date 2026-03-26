import useEmblaCarousel from 'embla-carousel-react'
import { useState } from 'react'

import {
  StyleAdsCard,
  StyleAdsCardSkeleton,
} from '@/components/ui/style-ads-card'
import { useCustomRank } from '@/hooks/Home/useCustomRank'
import { useToggleLike } from '@/hooks/Home/useToggleLike'

type CustomRankBannerProps = {
  onApply: (hairId: number) => void
}

export function CustomRankBanner({ onApply }: CustomRankBannerProps) {
  const { data: customRankData, isLoading, isError } = useCustomRank()
  const { mutate: toggleLike } = useToggleLike()
  const [likedOverrides, setLikedOverrides] = useState<Record<string, boolean>>(
    {},
  )
  const [emblaRef] = useEmblaCarousel()

  if (isLoading) {
    return <StyleAdsCardSkeleton className="w-full" />
  }

  if (isError) {
    return (
      <div className="flex h-[320px] w-full flex-col items-center justify-center rounded-lg bg-red-50 text-center text-sm font-medium text-red-500 shadow-sm">
        데이터를 불러오는 데 실패했습니다.
      </div>
    )
  }

  const customList = customRankData?.customList ?? []

  if (customList.length === 0) {
    return (
      <div className="flex h-[320px] w-full flex-col items-center justify-center rounded-lg bg-white text-center text-sm font-medium text-text-warm-300 shadow-sm">
        맞춤 추천 헤어가 없습니다. 🥲
      </div>
    )
  }

  return (
    <div className="overflow-hidden px-2 py-2" ref={emblaRef}>
      <div className="flex gap-3">
        {customList.map((item) => {
          const liked = likedOverrides[item.hairID.toString()] ?? item.liked
          return (
            <StyleAdsCard
              key={item.hairID}
              hairImgpath={item.image}
              hairSlug={item.hookText || '추천 헤어'}
              hairName={item.hairName}
              liked={liked}
              className="flex-[0_0_88%] shrink-0"
              onLikeToggle={() => {
                setLikedOverrides((prev) => ({
                  ...prev,
                  [item.hairID.toString()]: !liked,
                }))
                toggleLike(
                  { hairId: item.hairID, currentLiked: liked },
                  {
                    onSuccess: (data) =>
                      setLikedOverrides((prev) => ({
                        ...prev,
                        [data.hairID.toString()]: data.liked,
                      })),
                    onError: () =>
                      setLikedOverrides((prev) => ({
                        ...prev,
                        [item.hairID.toString()]: liked,
                      })),
                  },
                )
              }}
              onApply={() => onApply(item.hairID)}
            />
          )
        })}
      </div>
    </div>
  )
}
