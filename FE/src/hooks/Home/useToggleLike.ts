import { useMutation, useQueryClient } from '@tanstack/react-query'

import { addHairLike, removeHairLike } from '@/lib/hairs'
import type { CustomRankResponse, NormalRankResponse } from '@/lib/home'

type ToggleLikeParams = {
  hairId: number
  currentLiked: boolean
}

export function useToggleLike() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ hairId, currentLiked }: ToggleLikeParams) =>
      currentLiked ? removeHairLike(hairId) : addHairLike(hairId),

    onMutate: async ({ hairId, currentLiked }) => {
      await queryClient.cancelQueries({ queryKey: ['normalRank'] })
      await queryClient.cancelQueries({ queryKey: ['customRank'] })

      const prevNormalRank = queryClient.getQueryData<NormalRankResponse>([
        'normalRank',
      ])
      const prevCustomRankEntries =
        queryClient.getQueriesData<CustomRankResponse>({
          queryKey: ['customRank'],
        })

      const patch = <T extends { hairID: number; liked: boolean }>(
        item: T,
      ): T =>
        item.hairID === hairId ? { ...item, liked: !currentLiked } : item

      if (prevNormalRank) {
        queryClient.setQueryData<NormalRankResponse>(['normalRank'], {
          ...prevNormalRank,
          best: prevNormalRank.best.map(patch),
          latest: prevNormalRank.latest.map(patch),
        })
      }

      for (const [queryKey, data] of prevCustomRankEntries) {
        if (data) {
          queryClient.setQueryData<CustomRankResponse>(queryKey, {
            ...data,
            customList: data.customList.map(patch),
          })
        }
      }

      return { prevNormalRank, prevCustomRankEntries }
    },

    onError: (_err, _vars, context) => {
      if (context?.prevNormalRank) {
        queryClient.setQueryData(['normalRank'], context.prevNormalRank)
      }
      for (const [queryKey, data] of context?.prevCustomRankEntries ?? []) {
        queryClient.setQueryData(queryKey, data)
      }
    },

    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['likeList'] })
      queryClient.invalidateQueries({ queryKey: ['normalRank'] })
      queryClient.invalidateQueries({ queryKey: ['customRank'] })
    },
  })
}
