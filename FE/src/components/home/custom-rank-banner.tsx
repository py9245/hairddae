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
  const topCustomRank = customRankData?.customList?.[0]
  const { mutate: toggleLike } = useToggleLike()
  const [likedOverride, setLikedOverride] = useState<boolean | null>(null)
  const heroLiked = likedOverride ?? topCustomRank?.liked ?? false

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

  if (topCustomRank) {
    return (
      <StyleAdsCard
        hairImgpath={topCustomRank.image}
        hairSlug={topCustomRank.hookText || '추천 헤어'}
        hairName={topCustomRank.hairName}
        liked={heroLiked}
        className="w-full"
        onLikeToggle={() => {
          setLikedOverride(!heroLiked)
          toggleLike(
            { hairId: topCustomRank.hairID, currentLiked: heroLiked },
            {
              onSuccess: (data) => setLikedOverride(data.liked),
              onError: () => setLikedOverride(heroLiked),
            },
          )
        }}
        onApply={() => onApply(topCustomRank.hairID)}
      />
    )
  }

  return (
    <div className="flex h-[320px] w-full flex-col items-center justify-center rounded-lg bg-white text-center text-sm font-medium text-text-warm-300 shadow-sm">
      맞춤 추천 헤어가 없습니다. 🥲
    </div>
  )
}
