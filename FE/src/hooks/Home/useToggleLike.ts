import { useMutation, useQueryClient } from '@tanstack/react-query'

import { addHairLike, removeHairLike } from '@/lib/hairs'

type ToggleLikeParams = {
  hairId: number
  currentLiked: boolean
}

export function useToggleLike() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ hairId, currentLiked }: ToggleLikeParams) =>
      currentLiked ? removeHairLike(hairId) : addHairLike(hairId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['likeList'] })
    },
  })
}
