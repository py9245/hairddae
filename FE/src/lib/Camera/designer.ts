import { apiFetch } from '@/lib/api'

export type GetDesignerRequest = {
  latitude: number
  longitude: number
  hairId: number
}

export type GetDesignerResponse = {
  code: number
  message: string
}

export async function postGetDesigner({
  latitude,
  longitude,
  hairId,
}: GetDesignerRequest): Promise<GetDesignerResponse> {
  const response = await apiFetch('/camera/get-designer/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      latitude,
      longitude,
      hair_id: hairId,
    }),
  })

  const data = (await response.json().catch(() => null)) as {
    code?: number
    message?: string
  } | null

  if (!response.ok) {
    throw new Error(data?.message ?? '디자이너 목록 조회에 실패했습니다.')
  }

  return {
    code: data?.code ?? 200,
    message: data?.message ?? '디자이너 목록을 불러왔습니다.',
  }
}
