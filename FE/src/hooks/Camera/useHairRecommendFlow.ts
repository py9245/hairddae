import { useCallback, useRef, useState } from 'react'
import { buildApiUrl } from '@/lib/api'
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

  const requestRecommendation = useCallback(
    async ({
      hairID,
      yaw1deg,
      pitch1deg,
      roll1deg,
    }: RequestRecommendationArgs) => {
      setLoading(true)
      setError(null)

      try {
        const nextRecommendation = await fetchHairRecommend({
          baseUrl: recommendBaseUrl ?? buildApiUrl('/home/hairapply/'),
          fetchImpl,
          hairID,
          yaw1deg,
          pitch1deg,
          roll1deg,
        })

        setRecommendation(nextRecommendation)

        const asset = nextRecommendation.asset
        if (
          asset.hairRgbaUrl &&
          asset.assetID &&
          lastAssetIdRef.current !== asset.assetID
        ) {
          const image = await imageLoader(asset.hairRgbaUrl)
          lastAssetIdRef.current = asset.assetID
          setOverlayImage(image)
        }

        if (!asset.hairRgbaUrl) {
          lastAssetIdRef.current = null
          setOverlayImage(null)
        }

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
    [fetchImpl, imageLoader, recommendBaseUrl],
  )

  const requestByPose = useCallback(
    async (hairID: number, pose: PoseAngles) => {
      const rounded = roundPoseAngles(pose)
      return requestRecommendation({
        hairID,
        yaw1deg: rounded.yaw1deg,
        pitch1deg: rounded.pitch1deg,
        roll1deg: rounded.roll1deg,
      })
    },
    [requestRecommendation],
  )

  const buildFeatureMessage = useCallback(
    (args: BuildUserFeaturePayloadArgs): UserFeatureMessage =>
      buildUserFeaturePayload(args),
    [],
  )

  const clearRecommendation = useCallback(() => {
    lastAssetIdRef.current = null
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
  }
}
