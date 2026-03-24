import { apiFetch } from '@/lib/api'

export type HairClickResponse = {
  code: number
  message: string
  success: boolean
  hair_id: number
}

export async function postHairClick(
  hairId: number,
  viewSec = 0,
): Promise<HairClickResponse> {
  const response = await apiFetch('/home/hairclick/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      hair_id: hairId,
      view_sec: viewSec,
    }),
  })

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error(data?.message ?? '헤어 클릭 기록을 저장하지 못했습니다.')
  }

  return {
    code: typeof data?.code === 'number' ? data.code : 0,
    message: typeof data?.message === 'string' ? data.message : '',
    success: Boolean(data?.success),
    hair_id: typeof data?.hair_id === 'number' ? data.hair_id : hairId,
  }
}
