import { apiFetch } from './api'
import { postHairClick } from './hair-click'

export type MyPageHairItem = {
  hairID: number
  image: string
  liked: boolean
  hookText: string
  hairName: string
  category: string
  createdAt: string
}

export type LikeItem = MyPageHairItem

export type LikeListResponse = {
  code: number
  message: string
  userID: string
  likeList: LikeItem[]
}

export type AppliedItem = MyPageHairItem

export type AppliedListResponse = {
  code: number
  message: string
  totalCount: number
  hairList: AppliedItem[]
}

export async function getLikeList(): Promise<LikeListResponse> {
  const res = await apiFetch('/mypage/likelist', {
    method: 'GET',
  })

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    throw new Error(errorBody?.message ?? 'Failed to fetch like list')
  }

  return res.json()
}

export async function getAppliedList(): Promise<AppliedListResponse> {
  const res = await apiFetch('/mypage/appliedlist/', {
    method: 'GET',
  })

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    throw new Error(errorBody?.message ?? 'Failed to fetch applied list')
  }

  return res.json()
}

export async function applyMyPageHair(hairId: number): Promise<number> {
  const response = await postHairClick(hairId)

  return response.hair_id
}
