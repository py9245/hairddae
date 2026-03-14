import { z } from 'zod'
import type { HairRecommendResponse } from '@/contracts/recommend'
import type { PoseAngles } from '@/feature/pose'

const AssetIndexItemSchema = z.object({
  asset_id: z.string(),
  pose_key: z.string(),
  anchors_path: z.string(),
  metadata_path: z.string(),
  yaw_1deg: z.number().int(),
  pitch_1deg: z.number().int(),
  roll_1deg: z.number().int(),
  quality_score: z.number().nullable().optional(),
  approved: z.boolean().optional(),
})

const AssetIndexSchema = z.object({
  summary: z.object({
    total_assets: z.number().int(),
    approved_assets: z.number().int(),
  }),
  items: z.array(AssetIndexItemSchema),
})

const BoundingBoxSchema = z.object({
  x: z.number().int(),
  y: z.number().int(),
  w: z.number().int(),
  h: z.number().int(),
})

const AssetMetadataSchema = z.object({
  asset_id: z.string(),
  pose_key: z.string(),
  anchors_path: z.string(),
  image_size: z.object({
    width: z.number().int(),
    height: z.number().int(),
  }),
  face_bbox: BoundingBoxSchema,
  hair_rgba_path: z.string(),
  hair_rgba_bbox: BoundingBoxSchema,
})

const AnchorPointSchema = z.object({
  x: z.number(),
  y: z.number(),
  confidence: z.number().nullable().optional(),
})

const AssetAnchorMapSchema = z.object({
  forehead_center: AnchorPointSchema.nullable(),
  left_temple: AnchorPointSchema.nullable(),
  right_temple: AnchorPointSchema.nullable(),
  crown: AnchorPointSchema.nullable(),
  left_ear_root: AnchorPointSchema.nullable(),
  right_ear_root: AnchorPointSchema.nullable(),
  left_side: AnchorPointSchema.nullable(),
  right_side: AnchorPointSchema.nullable(),
  lower_left: AnchorPointSchema.nullable(),
  lower_right: AnchorPointSchema.nullable(),
  neck_left: AnchorPointSchema.nullable(),
  neck_right: AnchorPointSchema.nullable(),
})

const AssetAnchorsSchema = z.object({
  asset_id: z.string(),
  image_size: z.object({
    width: z.number().int(),
    height: z.number().int(),
  }),
  anchors: AssetAnchorMapSchema,
})

export type AssetIndex = z.infer<typeof AssetIndexSchema>
export type AssetIndexItem = z.infer<typeof AssetIndexItemSchema>
export type AssetMetadata = z.infer<typeof AssetMetadataSchema>
export type AssetAnchors = z.infer<typeof AssetAnchorsSchema>

export type AssetPackage = {
  item: AssetIndexItem
  metadata: AssetMetadata
  anchors: AssetAnchors
  image: HTMLImageElement
}

const assetIndexCache = new Map<string, Promise<AssetIndex>>()
const assetPackageCache = new Map<string, Promise<AssetPackage>>()

function defaultImageLoader(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image()
    image.crossOrigin = 'anonymous'
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error(`image load failed: ${src}`))
    image.src = src
  })
}

function normalizeStaticUrl(baseUrl: string, path: string) {
  const safeBase = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl
  const safePath = path.startsWith('/') ? path.slice(1) : path
  return `${safeBase}/${safePath}`
}

export async function loadAssetIndex(
  assetIndexUrl: string,
  fetchImpl: typeof fetch = fetch,
) {
  const cached = assetIndexCache.get(assetIndexUrl)
  if (cached) {
    return cached
  }

  const promise = (async () => {
    const response = await fetchImpl(assetIndexUrl)
    if (!response.ok) {
      throw new Error(`asset index request failed: ${response.status}`)
    }

    const json = (await response.json()) as unknown
    return AssetIndexSchema.parse(json)
  })()

  assetIndexCache.set(assetIndexUrl, promise)
  return promise
}

export async function loadAssetPackage(
  datasetRootUrl: string,
  item: AssetIndexItem,
  fetchImpl: typeof fetch = fetch,
  imageLoader: (src: string) => Promise<HTMLImageElement> = defaultImageLoader,
) {
  const cacheKey = `${datasetRootUrl}::${item.asset_id}`
  const cached = assetPackageCache.get(cacheKey)
  if (cached) {
    return cached
  }

  const promise = (async () => {
    const metadataUrl = normalizeStaticUrl(datasetRootUrl, item.metadata_path)
    const anchorsUrl = normalizeStaticUrl(datasetRootUrl, item.anchors_path)

    const [metadataResponse, anchorsResponse] = await Promise.all([
      fetchImpl(metadataUrl),
      fetchImpl(anchorsUrl),
    ])

    if (!metadataResponse.ok) {
      throw new Error(`asset metadata request failed: ${metadataResponse.status}`)
    }

    if (!anchorsResponse.ok) {
      throw new Error(`asset anchors request failed: ${anchorsResponse.status}`)
    }

    const metadataJson = (await metadataResponse.json()) as unknown
    const anchorsJson = (await anchorsResponse.json()) as unknown

    const metadata = AssetMetadataSchema.parse(metadataJson)
    const anchors = AssetAnchorsSchema.parse(anchorsJson)
    const image = await imageLoader(
      normalizeStaticUrl(datasetRootUrl, metadata.hair_rgba_path),
    )

    return {
      item,
      metadata,
      anchors,
      image,
    }
  })()

  assetPackageCache.set(cacheKey, promise)
  return promise
}

function poseDistance(item: AssetIndexItem, pose: PoseAngles) {
  const yaw = item.yaw_1deg - pose.yaw
  const pitch = item.pitch_1deg - pose.pitch
  const roll = item.roll_1deg - pose.roll

  return Math.abs(yaw) * 1.4 + Math.abs(pitch) * 1.1 + Math.abs(roll) * 0.8
}

export function findNearestAsset(items: AssetIndexItem[], pose: PoseAngles) {
  let best: AssetIndexItem | null = null
  let bestScore = Number.POSITIVE_INFINITY

  for (const item of items) {
    if (item.approved === false) continue

    const score = poseDistance(item, pose)
    if (score < bestScore) {
      best = item
      bestScore = score
    }
  }

  return best
}

export function buildAssetRuntimeRecommendation(
  hairID: number,
  hairName: string,
  datasetCode: string,
  datasetRootUrl: string,
  assetIndexUrl: string,
  assetPackage: AssetPackage,
): HairRecommendResponse {
  const hairRgbaUrl = normalizeStaticUrl(
    datasetRootUrl,
    assetPackage.metadata.hair_rgba_path,
  )
  const anchorsUrl = normalizeStaticUrl(
    datasetRootUrl,
    assetPackage.item.anchors_path,
  )
  const metadataUrl = normalizeStaticUrl(
    datasetRootUrl,
    assetPackage.item.metadata_path,
  )

  return {
    code: 200,
    message: '추천 정상',
    hairID,
    hairName,
    datasetCode,
    datasetRootUrl,
    assetIndexUrl,
    asset: {
      assetID: assetPackage.item.asset_id,
      poseKey: assetPackage.item.pose_key,
      yaw1deg: assetPackage.item.yaw_1deg,
      pitch1deg: assetPackage.item.pitch_1deg,
      roll1deg: assetPackage.item.roll_1deg,
      imageUrl: null,
      alphaUrl: null,
      anchorsUrl,
      metadataUrl,
      hairRgbaUrl,
      hairRgbaBBox: assetPackage.metadata.hair_rgba_bbox,
      qualityScore: assetPackage.item.quality_score ?? null,
    },
  }
}

export function prefetchNearestAssets(
  items: AssetIndexItem[],
  datasetRootUrl: string,
  pose: PoseAngles,
  fetchImpl: typeof fetch = fetch,
  imageLoader: (src: string) => Promise<HTMLImageElement> = defaultImageLoader,
  count = 4,
) {
  const nearest = [...items]
    .filter((item) => item.approved !== false)
    .sort((left, right) => poseDistance(left, pose) - poseDistance(right, pose))
    .slice(0, count)

  for (const item of nearest) {
    void loadAssetPackage(datasetRootUrl, item, fetchImpl, imageLoader).catch(
      () => {},
    )
  }
}
