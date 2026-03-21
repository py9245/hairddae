const BaseUrl = '/api'

export async function postHairClick(hairId: number, viewSec = 0) {
  const res = await fetch(`${BaseUrl}/home/hairclick/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({
      hair_id: hairId,
      view_sec: viewSec,
    }),
  })

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    throw new Error(data?.message ?? '헤어 클릭 기록을 저장하지 못했습니다.')
  }

  return data
}
