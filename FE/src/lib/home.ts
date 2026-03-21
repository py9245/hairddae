import { buildApiUrl } from './api'

export type CustomRankItem = {
  hairID: number
  image: string
  liked: boolean
  hookText: string
  hairName: string
  category: string
  createdAt: string
}

export type CustomRankResponse = {
  code: number
  message: string
  customList: CustomRankItem[]
}

export async function getCustomRank(size = 20): Promise<CustomRankResponse> {
  const res = await fetch(buildApiUrl(`/home/customrank?size=${size}`), {
    method: 'GET',
    credentials: 'include',
  })

  // 401 Unauthorized handling could be managed globally or by throwing an error
  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    throw new Error(errorBody?.message ?? 'Failed to fetch custom rank')
  }

  return res.json()
}
