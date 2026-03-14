import { useCallback, useRef, useState } from 'react'
import { buildApiUrl } from '@/lib/api'
import {
  type AssetIndex,
  type AssetPackage,
  buildAssetRuntimeRecommendation,
  findNearestAsset,
  loadAssetIndex,
  loadAssetPackage,
  prefetchNearestAssets,
} from '@/lib/Camera/assetRuntime'
import type { UserFeatureMessage } from '@/lib/Camera/contracts'
import {
  type BuildUserFeaturePayloadArgs,
  buildUserFeaturePayload,
} from '@/lib/Camera/feature'
import {
  type FetchHairRecommendArgs,
  fetchHairRecommend,
  type HairRecommendResponse,
} from '@/lib/Camera/recommend'
import type { PoseAngles } from '@/lib/Camera/types'

type UseHairRecommendFlowArgs = {
  recommendBaseUrl?: string
  fetchImpl?: typeof fetch
  imageLoader?: (src: string) => Promise<HTMLImageElement>
}

type RequestRecommendationArgs = Omit<
  FetchHairRecommendArgs,
  'baseUrl' | 'fetchImpl'
>

type HairRuntime = {
  hairID: number
  hairName: string
  datasetCode: string
  datasetRootUrl: string
  assetIndexUrl: string
  assetIndex: AssetIndex
}

function roundPoseAngles(pose: PoseAngles) {
  return {
    yaw1deg: Math.round(pose.yaw),
    pitch1deg: Math.round(pose.pitch),
    roll1deg: Math.round(pose.roll),
  }
}

function defaultImageLoader(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image()
    image.crossOrigin = 'anonymous'
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error(`image load failed: ${src}`))
    image.src = src
  })
}

export function useHairRecommendFlow({
  recommendBaseUrl,
  fetchImpl = fetch,
  imageLoader = defaultImageLoader,
}: UseHairRecommendFlowArgs = {}) {
  const [recommendation, setRecommendation] =
    useState<HairRecommendResponse | null>(null)
  const [overlayImage, setOverlayImage] = useState<HTMLImageElement | null>(
    null,
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const lastAssetIdRef = useRef<string | null>(null)
  const lastRecommendationRef = useRef<HairRecommendResponse | null>(null)
  const lastAssetSwitchAtRef = useRef(0)
  const runtimeRef = useRef<HairRuntime | null>(null)
  const activeAssetRef = useRef<AssetPackage | null>(null)

  const ensureRuntime = useCallback(
    async ({ hairID, yaw1deg, pitch1deg, roll1deg }: RequestRecommendationArgs) => {
      if (runtimeRef.current?.hairID === hairID) {
        return runtimeRef.current
      }

      const baseUrl = recommendBaseUrl ?? buildApiUrl('/hairs/recommend')
      const bootstrap = await fetchHairRecommend({
        baseUrl,
        fetchImpl,
        hairID,
        yaw1deg,
        pitch1deg,
        roll1deg,
      })

      const assetIndex = await loadAssetIndex(bootstrap.assetIndexUrl, fetchImpl)

      const nextRuntime: HairRuntime = {
        hairID: bootstrap.hairID,
        hairName: bootstrap.hairName,
        datasetCode: bootstrap.datasetCode,
        datasetRootUrl: bootstrap.datasetRootUrl,
        assetIndexUrl: bootstrap.assetIndexUrl,
        assetIndex,
      }

      runtimeRef.current = nextRuntime
      return nextRuntime
    },
    [fetchImpl, recommendBaseUrl],
  )

  const requestRecommendation = useCallback(
    async ({
      hairID,
      yaw1deg,
      pitch1deg,
      roll1deg,
    }: RequestRecommendationArgs) => {
      try {
        setLoading(true)
        setError(null)

        const runtime = await ensureRuntime({
          hairID,
          yaw1deg,
          pitch1deg,
          roll1deg,
        })

        const nearest = findNearestAsset(runtime.assetIndex.items, {
          yaw: yaw1deg ?? 0,
          pitch: pitch1deg ?? 0,
          roll: roll1deg ?? 0,
        })
        if (!nearest) {
          throw new Error('no approved asset found for current pose')
        }

        const assetPackage = await loadAssetPackage(
          runtime.datasetRootUrl,
          nearest,
          fetchImpl,
          imageLoader,
        )

        activeAssetRef.current = assetPackage
        lastAssetIdRef.current = assetPackage.item.asset_id
        lastAssetSwitchAtRef.current = Date.now()

        const nextRecommendation = buildAssetRuntimeRecommendation(
          runtime.hairID,
          runtime.hairName,
          runtime.datasetCode,
          runtime.datasetRootUrl,
          runtime.assetIndexUrl,
          assetPackage,
        )

        setRecommendation(nextRecommendation)
        setOverlayImage(assetPackage.image)
        lastRecommendationRef.current = nextRecommendation

        return nextRecommendation
      } catch (caught) {
        const message =
          caught instanceof Error ? caught.message : 'recommendation failed'
        setError(message)
        throw caught
      } finally {
        setLoading(false)
      }
    },
    [ensureRuntime, fetchImpl, imageLoader],
  )

  const requestByPose = useCallback(
    async (hairID: number, pose: PoseAngles) => {
      const rounded = roundPoseAngles(pose)

      const runtime = await ensureRuntime({
        hairID,
        yaw1deg: rounded.yaw1deg,
        pitch1deg: rounded.pitch1deg,
        roll1deg: rounded.roll1deg,
      })

      const now = Date.now()
      const nearest = findNearestAsset(runtime.assetIndex.items, {
        yaw: rounded.yaw1deg,
        pitch: rounded.pitch1deg,
        roll: rounded.roll1deg,
      })

      if (!nearest) {
        return lastRecommendationRef.current
      }

      prefetchNearestAssets(
        runtime.assetIndex.items,
        runtime.datasetRootUrl,
        {
          yaw: rounded.yaw1deg,
          pitch: rounded.pitch1deg,
          roll: rounded.roll1deg,
        },
        fetchImpl,
        imageLoader,
      )

      if (lastAssetIdRef.current === nearest.asset_id) {
        return lastRecommendationRef.current
      }

      if (now - lastAssetSwitchAtRef.current < 80) {
        return lastRecommendationRef.current
      }

      return requestRecommendation({
        hairID,
        yaw1deg: rounded.yaw1deg,
        pitch1deg: rounded.pitch1deg,
        roll1deg: rounded.roll1deg,
      })
    },
    [ensureRuntime, fetchImpl, imageLoader, requestRecommendation],
  )

  const buildFeatureMessage = useCallback(
    (args: BuildUserFeaturePayloadArgs): UserFeatureMessage =>
      buildUserFeaturePayload(args),
    [],
  )

  const clearRecommendation = useCallback(() => {
    lastAssetIdRef.current = null
    lastRecommendationRef.current = null
    lastAssetSwitchAtRef.current = 0
    runtimeRef.current = null
    activeAssetRef.current = null
    setRecommendation(null)
    setOverlayImage(null)
    setLoading(false)
    setError(null)
  }, [])

  return {
    recommendation,
    overlayImage,
    loading,
    error,
    requestRecommendation,
    requestByPose,
    buildFeatureMessage,
    clearRecommendation,
    activeAsset: activeAssetRef.current,
  }
}
