import { buildApiUrl } from '@/lib/api'

export type HairApplyStartResponse = {
  message: string
  applySessionId: string
  success: boolean
  code: number
}

export async function postHairApplyStart(
  hairId: number,
): Promise<HairApplyStartResponse | null> {
  const res = await fetch(buildApiUrl('/home/hairapplystart/'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ hairID: hairId }),
  })

  if (!res.ok) {
    let message = '헤어 적용 시작 요청에 실패했어요.'

    try {
      const data = await res.json()
      if (data?.message) message = data.message
    } catch {}

    throw new Error(message)
  }

  return await res.json()
}
