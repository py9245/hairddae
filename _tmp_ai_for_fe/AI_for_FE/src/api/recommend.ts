import {
  HairRecommendResponseSchema,
  type HairRecommendResponse,
} from '@/contracts/recommend'

export type FetchHairRecommendArgs = {
  baseUrl?: string
  hairID: number
  yaw1deg?: number
  pitch1deg?: number
  roll1deg?: number
  fetchImpl?: typeof fetch
}

export async function fetchHairRecommend({
  baseUrl = '/api/hairs/recommend',
  hairID,
  yaw1deg,
  pitch1deg,
  roll1deg,
  fetchImpl = fetch,
}: FetchHairRecommendArgs): Promise<HairRecommendResponse> {
  const params = new URLSearchParams({
    hairId: String(hairID),
  })

  if (yaw1deg !== undefined) params.set('yaw1deg', String(yaw1deg))
  if (pitch1deg !== undefined) params.set('pitch1deg', String(pitch1deg))
  if (roll1deg !== undefined) params.set('roll1deg', String(roll1deg))

  const response = await fetchImpl(`${baseUrl}?${params.toString()}`)
  if (!response.ok) {
    throw new Error(`recommend request failed: ${response.status}`)
  }

  const json = (await response.json()) as unknown
  return HairRecommendResponseSchema.parse(json)
}
