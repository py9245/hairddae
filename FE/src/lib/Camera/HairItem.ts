import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'
import { apiFetch } from '@/lib/api'

export type HairItem = {
  id: number
  image: string
  label: string
  datasetCode?: string | null
}

export const HAIR_ITEMS: HairItem[] = [
  {
    id: 0,
    image: '',
    label: 'None',
    datasetCode: null,
  },
]

const HairCardSchema = z.object({
  hairID: z.number().int(),
  image: z.string(),
  hairName: z.string(),
  datasetCode: z.string().nullable().optional(),
  dataset_code: z.string().nullable().optional(),
})

const HairListResponseSchema = z.object({
  hairList: z.array(HairCardSchema),
})

export async function fetchHairItems(
  signal?: AbortSignal,
): Promise<HairItem[]> {
  const response = await apiFetch('/mypage/appliedlist/', {
    method: 'GET',
    signal,
  })

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error(data?.message ?? '헤어 목록을 불러오지 못했습니다.')
  }

  const payload = HairListResponseSchema.parse(data)

  return [
    HAIR_ITEMS[0],
    ...payload.hairList.map((item) => {
      return {
        id: item.hairID,
        image: item.image,
        label: item.hairName,
        datasetCode: item.datasetCode ?? item.dataset_code ?? null,
      }
    }),
  ]
}

export const hairItemsQueryOptions = () =>
  queryOptions({
    queryKey: ['hair-items'],
    queryFn: ({ signal }) => fetchHairItems(signal),
    staleTime: 1000 * 60 * 5,
  })
