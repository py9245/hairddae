import { useQuery } from '@tanstack/react-query'

import { auth, fetchMe, ME_QUERY_KEY, ME_QUERY_STALE_TIME } from '@/lib/auth'

export function useMe() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      const data = await fetchMe()
      return data
    },
    enabled: auth.isAuthenticated(),
    retry: false,
    staleTime: ME_QUERY_STALE_TIME,
  })
}
