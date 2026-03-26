import { useQuery } from '@tanstack/react-query'
import { getCustomRank } from '@/lib/home'

export function useCustomRank(size = 20) {
  return useQuery({
    queryKey: ['customRank', size],
    queryFn: () => getCustomRank(size),
  })
}
