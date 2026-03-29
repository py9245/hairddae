import { useQuery } from '@tanstack/react-query'

import { getAppliedList } from '@/lib/mypage'

export function useAppliedList() {
  return useQuery({
    queryKey: ['appliedList'],
    queryFn: getAppliedList,
  })
}
