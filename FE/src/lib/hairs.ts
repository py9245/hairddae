import { buildApiUrl } from '@/lib/api'

export type HairLikeResponse = {
  code: number
  message: string
  hairID: number
  liked: boolean
  likeCount: number
}

async function requestHairLike(
  hairId: number,
  method: 'POST' | 'DELETE',
): Promise<HairLikeResponse> {
  const res = await fetch(buildApiUrl(`/hairs/${hairId}/like/`), {
    method,
    credentials: 'include',
  })

  if (!res.ok) {
    let message = '찜하기 처리에 실패했습니다.'
    try {
      const errorBody = await res.json()
      if (errorBody?.message) message = errorBody.message
    } catch (e) {
      throw new Error(`${message} (응답 파싱 실패: ${e instanceof Error ? e.message : String(e)})`)
    }
    throw new Error(message)
  }

  return res.json() as Promise<HairLikeResponse>
}

export function addHairLike(hairId: number): Promise<HairLikeResponse> {
  return requestHairLike(hairId, 'POST')
}

export function removeHairLike(hairId: number): Promise<HairLikeResponse> {
  return requestHairLike(hairId, 'DELETE')
}
