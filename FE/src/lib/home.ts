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

export type CategoryItem = {
  categoryID: string
  categoryName: string
  image: string
}

export type CategoryListResponse = {
  code: number
  message: string
  categoryList: CategoryItem[]
}

export async function getCategoryList(): Promise<CategoryListResponse> {
  const res = await fetch(buildApiUrl(`/home/categorylist/`), {
    method: 'GET',
    credentials: 'include',
  })

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    throw new Error(errorBody?.message ?? 'Failed to fetch category list')
  }

  return res.json()
}

export type HairCardItem = {
  hairID: number
  image: string
  liked: boolean
  hookText: string
  hairName: string
  category: string
  createdAt: string
}

export type CategoryCardListResponse = {
  code: number
  message: string
  categoryID: string
  categoryName: string
  cardList: HairCardItem[]
}

export async function getCategoryCardList(
  categoryId?: string,
  size = 50,
): Promise<CategoryCardListResponse> {
  const url = categoryId
    ? `/home/categorycardlist?categoryId=${categoryId}&size=${size}`
    : `/home/categorycardlist?size=${size}`

  const res = await fetch(buildApiUrl(url), {
    method: 'GET',
    credentials: 'include',
  })

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null)
    throw new Error(errorBody?.message ?? 'Failed to fetch category card list')
  }

  return res.json()
}
