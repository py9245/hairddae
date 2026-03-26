import { useQuery } from '@tanstack/react-query'

import { getLikeList } from '@/lib/mypage'

export function useLikeList() {
  return useQuery({
    queryKey: ['likeList'],
    queryFn: getLikeList,
  })
}
