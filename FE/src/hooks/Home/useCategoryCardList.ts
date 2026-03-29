import { useQuery } from '@tanstack/react-query'
import { getCategoryCardList } from '@/lib/home'

export function useCategoryCardList(categoryId?: string) {
  return useQuery({
    queryKey: ['categoryCardList', categoryId],
    queryFn: () => getCategoryCardList(categoryId),
  })
}
