import { queryOptions } from '@tanstack/react-query'
import { z } from 'zod'

const BaseUrl = '/api'

export type HairItem = {
  id: number
  img: string
  thumb: string
  label: string
  datasetCode?: string | null
}

export const HAIR_ITEMS: HairItem[] = [
  {
    id: 0,
    img: '',
    thumb: '',
    label: 'None',
    datasetCode: null,
  },
]

const HairCardSchema = z.object({
  hairID: z.number().int(),
  hairName: z.string(),
  hairImgpath: z.string(),
  datasetCode: z.string().optional().nullable(),
})

const HairListResponseSchema = z.object({
  hairList: z.array(HairCardSchema),
})

function resolveHairAssetUrl(path: string) {
  if (!path) return ''
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path
  }
  return `${BaseUrl}${path}`
}

export async function fetchHairItems(
  signal?: AbortSignal,
): Promise<HairItem[]> {
  const res = await fetch(`${BaseUrl}/hairs/`, {
    method: 'GET',
    credentials: 'include',
    signal,
  })

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    throw new Error(data?.message ?? '헤어 목록을 불러오지 못했습니다.')
  }

  const payload = HairListResponseSchema.parse(data)

  return [
    HAIR_ITEMS[0],
    ...payload.hairList.map((item) => ({
      id: item.hairID,
      img: resolveHairAssetUrl(item.hairImgpath),
      thumb: resolveHairAssetUrl(item.hairImgpath),
      label: item.hairName,
      datasetCode: item.datasetCode ?? null,
    })),
  ]
}

export const hairItemsQueryOptions = () =>
  queryOptions({
    queryKey: ['hair-items'],
    queryFn: ({ signal }) => fetchHairItems(signal),
    staleTime: 1000 * 60 * 5,
  })