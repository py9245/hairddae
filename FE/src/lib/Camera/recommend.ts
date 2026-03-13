import { z } from 'zod'
import { buildApiUrl } from '@/lib/api'

export const HairRgbaBBoxSchema = z.object({
  x: z.number().int(),
  y: z.number().int(),
  w: z.number().int(),
  h: z.number().int(),
})

export const RecommendedAssetSchema = z.object({
  assetID: z.string(),
  poseKey: z.string(),
  yaw1deg: z.number().int().nullable(),
  pitch1deg: z.number().int().nullable(),
  roll1deg: z.number().int().nullable(),
  imageUrl: z.string().nullable(),
  alphaUrl: z.string().nullable(),
  anchorsUrl: z.string().nullable(),
  metadataUrl: z.string().nullable(),
  hairRgbaUrl: z.string().nullable(),
  hairRgbaBBox: HairRgbaBBoxSchema.nullable(),
  qualityScore: z.number().nullable(),
})

export const HairRecommendResponseSchema = z.object({
  code: z.number().int(),
  message: z.string(),
  hairID: z.number().int(),
  hairName: z.string(),
  datasetCode: z.string(),
  datasetRootUrl: z.string(),
  assetIndexUrl: z.string(),
  asset: RecommendedAssetSchema,
})

export type HairRgbaBBox = z.infer<typeof HairRgbaBBoxSchema>
export type HairRecommendResponse = z.infer<typeof HairRecommendResponseSchema>

export type FetchHairRecommendArgs = {
  baseUrl?: string
  hairID: number
  yaw1deg?: number
  pitch1deg?: number
  roll1deg?: number
  fetchImpl?: typeof fetch
}

export async function fetchHairRecommend({
  baseUrl = buildApiUrl('/hairs/recommend'),
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
