import { useQuery } from '@tanstack/react-query'
import { getNormalRank } from '@/lib/home'

export function useNormalRank() {
  return useQuery({
    queryKey: ['normalRank'],
    queryFn: getNormalRank,
  })
}
