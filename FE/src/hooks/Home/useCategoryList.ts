import { useQuery } from '@tanstack/react-query'
import { getCategoryList } from '@/lib/home'

export function useCategoryList() {
  return useQuery({
    queryKey: ['categoryList'],
    queryFn: getCategoryList,
  })
}
