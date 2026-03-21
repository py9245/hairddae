import { useQuery } from '@tanstack/react-query'

import { fetchMe } from '@/lib/auth'

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const data = await fetchMe()
      return data
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
}
