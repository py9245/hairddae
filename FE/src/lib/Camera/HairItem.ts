import { z } from 'zod'

import { buildApiUrl } from '@/lib/api'

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
  {
    id: 1,
    img: '/hair/hair.png',
    thumb: '/hair/hair.png',
    label: 'Hair 1',
    datasetCode: '0001',
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

export async function fetchHairItems(
  signal?: AbortSignal,
): Promise<HairItem[]> {
  const response = await fetch(buildApiUrl('/hairs?page=0&size=20&sort=id'), {
    credentials: 'include',
    signal,
  })

  if (!response.ok) {
    throw new Error(`hair list load failed: ${response.status}`)
  }

  const payload = HairListResponseSchema.parse(
    (await response.json()) as unknown,
  )
  return [
    HAIR_ITEMS[0],
    ...payload.hairList.map((item) => ({
      id: item.hairID,
      img: item.hairImgpath,
      thumb: item.hairImgpath,
      label: item.hairName,
      datasetCode: item.datasetCode ?? null,
    })),
  ]
}
