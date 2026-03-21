import { useState } from 'react'

import {
  StyleAdsCard,
  StyleAdsCardSkeleton,
} from '@/components/ui/style-ads-card'
import { useCustomRank } from '@/hooks/Home/useCustomRank'

type CustomRankBannerProps = {
  onApply: (hairId: number) => void
}

export function CustomRankBanner({ onApply }: CustomRankBannerProps) {
  const { data: customRankData, isLoading, isError } = useCustomRank()
  const topCustomRank = customRankData?.customList?.[0]
  const [heroLiked, setHeroLiked] = useState(true)

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
        onLikeToggle={() => setHeroLiked((prev) => !prev)}
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
