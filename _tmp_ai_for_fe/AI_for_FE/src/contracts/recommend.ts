import { z } from 'zod'

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
export type RecommendedAsset = z.infer<typeof RecommendedAssetSchema>
export type HairRecommendResponse = z.infer<typeof HairRecommendResponseSchema>
