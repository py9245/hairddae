import { buildApiUrl } from './api'

export type LikeItem = {
  hairID: number
  image: string
  liked: boolean
  hookText: string
  hairName: string
  category: string
  createdAt: string
}

export type LikeListResponse = {
  code: number
  message: string
  userID: string
  likeList: LikeItem[]
}

export async function getLikeList(): Promise<LikeListResponse> {
  const res = await fetch(buildApiUrl('/mypage/likelist'), {
    method: 'GET',
    credentials: 'include',
  })

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    throw new Error(errorBody?.message ?? 'Failed to fetch like list')
  }

  return res.json()
}
