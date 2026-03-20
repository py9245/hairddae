import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { z } from 'zod'
import { buildApiUrl } from '@/lib/api'
import { getStoredAccessToken } from '@/lib/auth'
import {
  buildFaceAnchorPoints,
  buildFaceBoundingBox,
} from '@/lib/Camera/anchors'
import type { PoseAngles } from '@/lib/Camera/types'

const DEVICE_ID_STORAGE_KEY = 'hairapply-device-id'
export const INFERENCE_WS_PROTOCOL = 'hairapply.v2'

const BoundingBoxSchema = z.object({
  x: z.number().int(),
  y: z.number().int(),
  w: z.number().int(),
  h: z.number().int(),
})

const RenderPointSchema = z.object({
  x: z.number(),
  y: z.number(),
})

const RenderMatrixSchema = z.object({
  a: z.number(),
  b: z.number(),
  c: z.number(),
  d: z.number(),
  e: z.number(),
  f: z.number(),
})

const RenderTaskSchema = z.object({
  render_task_schema_version: z.number().int(),
  mode: z.literal('affine_crop_v1'),
  source_crop: BoundingBoxSchema,
  destination_roi: BoundingBoxSchema,
  destination_quad: z.array(RenderPointSchema).length(4),
  matrix: RenderMatrixSchema,
})

const RawInferenceAssetBundleSchema = z.object({
  asset_bundle_schema_version: z.number().int(),
  asset_id: z.string(),
  pose_key: z.string(),
  yaw_1deg: z.number().int(),
  pitch_1deg: z.number().int(),
  roll_1deg: z.number().int(),
  hair_rgba_url: z.string().nullable(),
  hair_mask_url: z.string().nullable(),
  anchors_url: z.string().nullable(),
  metadata_url: z.string().nullable(),
  hair_bbox: BoundingBoxSchema.nullable(),
  face_mask_url: z.string().nullable(),
  protect_face_mask_url: z.string().nullable(),
  render_task: RenderTaskSchema.nullable(),
  revision: z.string(),
  score: z.number(),
})

const RawConnectedMessageSchema = z.object({
  type: z.literal('connected'),
  apply_session_id: z.string(),
  node_id: z.string(),
  feature_schema_version: z.number().int(),
  transform_version: z.string(),
})

const RawProcessedMessageSchema = z.object({
  type: z.literal('processed'),
  apply_session_id: z.string(),
  accepted_seq: z.number().int(),
  processed_seq: z.number().int(),
  changed: z.boolean(),
  queue_depth: z.number().int(),
  dropped_pending_count: z.number().int(),
  overloaded: z.boolean(),
  asset: RawInferenceAssetBundleSchema,
})

const RawHeartbeatAckMessageSchema = z.object({
  type: z.literal('heartbeat_ack'),
  apply_session_id: z.string(),
  ts_ms: z.number().int(),
})

const RawErrorMessageSchema = z.object({
  type: z.literal('error'),
  code: z.number().int(),
  message: z.string(),
})

const RawHairApplyV2ResponseSchema = z.object({
  code: z.number().int(),
  message: z.string(),
  success: z.boolean(),
  apply_session_id: z.string(),
  feature_schema_version: z.number().int(),
  transform_version: z.string(),
  inference: z.object({
    ws_url: z.string(),
    ws_auth_transport: z.string(),
    connect_ticket: z.string(),
    expires_at: z.string(),
    node_id: z.string(),
    processed_timeout_ms: z.number().int(),
    heartbeat_interval_ms: z.number().int(),
    idle_ttl_ms: z.number().int(),
  }),
  rtc: z.object({
    enabled: z.boolean(),
    offer_url: z.string(),
    connect_ticket: z.string(),
    expires_at: z.string(),
    ice_servers: z.array(
      z.object({
        urls: z.array(z.string()),
        username: z.string().nullable().optional(),
        credential: z.string().nullable().optional(),
      }),
    ),
  }),
  static: z.object({
    base_url: z.string(),
    dataset_code: z.string(),
    asset_bundle_schema_version: z.number().int(),
    asset_index_url: z.string(),
    preload_asset_ids: z.array(z.string()),
  }),
})

const RawHairAssetIndexItemSchema = z.object({
  asset_id: z.string(),
  pose_key: z.string(),
  hair_rgba_url: z.string().nullable(),
  hair_mask_url: z.string().nullable(),
  anchors_url: z.string().nullable(),
  metadata_url: z.string().nullable(),
  hair_bbox: BoundingBoxSchema.nullable(),
  revision: z.string(),
})

const RawHairAssetIndexResponseSchema = z.object({
  code: z.number().int(),
  message: z.string(),
  hair_id: z.number().int(),
  dataset_code: z.string(),
  asset_bundle_schema_version: z.number().int(),
  items: z.array(RawHairAssetIndexItemSchema),
})

export type InferenceRenderTask = {
  renderTaskSchemaVersion: number
  mode: 'affine_crop_v1'
  sourceCrop: { x: number; y: number; w: number; h: number }
  destinationRoi: { x: number; y: number; w: number; h: number }
  destinationQuad: Array<{ x: number; y: number }>
  matrix: { a: number; b: number; c: number; d: number; e: number; f: number }
}

export type InferenceAssetBundle = {
  assetBundleSchemaVersion: number
  assetId: string
  poseKey: string
  yaw1deg: number
  pitch1deg: number
  roll1deg: number
  hairRgbaUrl: string | null
  hairMaskUrl: string | null
  anchorsUrl: string | null
  metadataUrl: string | null
  hairBBox: { x: number; y: number; w: number; h: number } | null
  faceMaskUrl: string | null
  protectFaceMaskUrl: string | null
  renderTask: InferenceRenderTask | null
  revision: string
  score: number
}

export type HairApplyV2Response = {
  code: number
  message: string
  success: boolean
  applySessionId: string
  featureSchemaVersion: number
  transformVersion: string
  inference: {
    wsUrl: string
    wsAuthTransport: string
    connectTicket: string
    expiresAt: string
    nodeId: string
    processedTimeoutMs: number
    heartbeatIntervalMs: number
    idleTtlMs: number
  }
  rtc: {
    enabled: boolean
    offerUrl: string
    connectTicket: string
    expiresAt: string
    iceServers: Array<{
      urls: string[]
      username?: string | null
      credential?: string | null
    }>
  }
  static: {
    baseUrl: string
    datasetCode: string
    assetBundleSchemaVersion: number
    assetIndexUrl: string
    preloadAssetIds: string[]
  }
}

export type HairAssetIndexBundle = {
  assetId: string
  poseKey: string
  hairRgbaUrl: string | null
  hairMaskUrl: string | null
  anchorsUrl: string | null
  metadataUrl: string | null
  hairBBox: { x: number; y: number; w: number; h: number } | null
  revision: string
}

export type HairAssetIndexResponse = {
  code: number
  message: string
  hairId: number
  datasetCode: string
  assetBundleSchemaVersion: number
  items: HairAssetIndexBundle[]
}

export type RtcOfferResponse = {
  sdp: string
  type: RTCSdpType
}

export type InferenceConnectedMessage = {
  type: 'connected'
  applySessionId: string
  nodeId: string
  featureSchemaVersion: number
  transformVersion: string
}

export type InferenceProcessedMessage = {
  type: 'processed'
  applySessionId: string
  acceptedSeq: number
  processedSeq: number
  changed: boolean
  queueDepth: number
  droppedPendingCount: number
  overloaded: boolean
  asset: InferenceAssetBundle
}

export type InferenceHeartbeatAckMessage = {
  type: 'heartbeat_ack'
  applySessionId: string
  tsMs: number
}

export type InferenceErrorMessage = {
  type: 'error'
  code: number
  message: string
}

export type InferenceIncomingMessage =
  | InferenceConnectedMessage
  | InferenceProcessedMessage
  | InferenceHeartbeatAckMessage
  | InferenceErrorMessage

export type InferenceFeatureMessage = {
  type: 'feature'
  feature_schema_version: number
  coordinate_space: 'pixel_v1'
  anchor_set: 'face_anchor_v1'
  transform_version: string
  seq: number
  ts_ms: number
  apply_session_id: string
  hair_id: number
  image_size: {
    width: number
    height: number
  }
  pose: {
    yaw_float: number
    pitch_float: number
    roll_float: number
    yaw_1deg: number
    pitch_1deg: number
    roll_1deg: number
  }
  face_bbox: {
    x: number
    y: number
    w: number
    h: number
  }
  anchors: ReturnType<typeof buildFaceAnchorPoints>
}

function normalizeAsset(
  raw: z.infer<typeof RawInferenceAssetBundleSchema>,
): InferenceAssetBundle {
  return {
    assetBundleSchemaVersion: raw.asset_bundle_schema_version,
    assetId: raw.asset_id,
    poseKey: raw.pose_key,
    yaw1deg: raw.yaw_1deg,
    pitch1deg: raw.pitch_1deg,
    roll1deg: raw.roll_1deg,
    hairRgbaUrl: raw.hair_rgba_url,
    hairMaskUrl: raw.hair_mask_url,
    anchorsUrl: raw.anchors_url,
    metadataUrl: raw.metadata_url,
    hairBBox: raw.hair_bbox,
    faceMaskUrl: raw.face_mask_url,
    protectFaceMaskUrl: raw.protect_face_mask_url,
    renderTask: raw.render_task
      ? {
          renderTaskSchemaVersion: raw.render_task.render_task_schema_version,
          mode: raw.render_task.mode,
          sourceCrop: raw.render_task.source_crop,
          destinationRoi: raw.render_task.destination_roi,
          destinationQuad: raw.render_task.destination_quad,
          matrix: raw.render_task.matrix,
        }
      : null,
    revision: raw.revision,
    score: raw.score,
  }
}

function normalizeHairAssetIndexBundle(
  raw: z.infer<typeof RawHairAssetIndexItemSchema>,
): HairAssetIndexBundle {
  return {
    assetId: raw.asset_id,
    poseKey: raw.pose_key,
    hairRgbaUrl: raw.hair_rgba_url,
    hairMaskUrl: raw.hair_mask_url,
    anchorsUrl: raw.anchors_url,
    metadataUrl: raw.metadata_url,
    hairBBox: raw.hair_bbox,
    revision: raw.revision,
  }
}

function resolveLocalRtcOfferUrl(rawOfferUrl: string): string {
  if (typeof window === 'undefined') {
    return rawOfferUrl
  }

  const hostname = window.location.hostname
  const isLocalhost = hostname === '127.0.0.1' || hostname === 'localhost'
  if (!isLocalhost) {
    return rawOfferUrl
  }

  return `${window.location.origin}/rtc/inference/offer`
}

function normalizeBootstrap(
  raw: z.infer<typeof RawHairApplyV2ResponseSchema>,
): HairApplyV2Response {
  return {
    code: raw.code,
    message: raw.message,
    success: raw.success,
    applySessionId: raw.apply_session_id,
    featureSchemaVersion: raw.feature_schema_version,
    transformVersion: raw.transform_version,
    inference: {
      wsUrl: raw.inference.ws_url,
      wsAuthTransport: raw.inference.ws_auth_transport,
      connectTicket: raw.inference.connect_ticket,
      expiresAt: raw.inference.expires_at,
      nodeId: raw.inference.node_id,
      processedTimeoutMs: raw.inference.processed_timeout_ms,
      heartbeatIntervalMs: raw.inference.heartbeat_interval_ms,
      idleTtlMs: raw.inference.idle_ttl_ms,
    },
    rtc: {
      enabled: raw.rtc.enabled,
      offerUrl: resolveLocalRtcOfferUrl(raw.rtc.offer_url),
      connectTicket: raw.rtc.connect_ticket,
      expiresAt: raw.rtc.expires_at,
      iceServers: raw.rtc.ice_servers.map((server) => ({
        urls: server.urls,
        username: server.username,
        credential: server.credential,
      })),
    },
    static: {
      baseUrl: raw.static.base_url,
      datasetCode: raw.static.dataset_code,
      assetBundleSchemaVersion: raw.static.asset_bundle_schema_version,
      assetIndexUrl: raw.static.asset_index_url,
      preloadAssetIds: raw.static.preload_asset_ids,
    },
  }
}

export async function postRtcOffer({
  offerUrl,
  connectTicket,
  localDescription,
  signal,
}: {
  offerUrl: string
  connectTicket: string
  localDescription: RTCSessionDescriptionInit
  signal?: AbortSignal
}): Promise<RtcOfferResponse> {
  if (!localDescription.sdp || !localDescription.type) {
    throw new Error('RTC offer is missing')
  }

  const response = await fetch(offerUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    signal,
    body: JSON.stringify({
      sdp: localDescription.sdp,
      type: localDescription.type,
      connect_ticket: connectTicket,
    }),
  })

  if (!response.ok) {
    let message = 'RTC 연결 협상에 실패했습니다.'

    try {
      const json = (await response.json()) as {
        detail?: string
        message?: string
      }
      if (json.detail) {
        message = json.detail
      } else if (json.message) {
        message = json.message
      }
    } catch {}

    throw new Error(message)
  }

  return z
    .object({
      sdp: z.string(),
      type: z.enum(['answer', 'offer', 'pranswer', 'rollback']),
    })
    .parse((await response.json()) as unknown)
}

export async function fetchHairAssetIndex(
  assetIndexUrl: string,
  signal?: AbortSignal,
): Promise<HairAssetIndexResponse> {
  const response = await fetch(assetIndexUrl, {
    credentials: 'include',
    signal,
  })

  if (!response.ok) {
    throw new Error(`asset index load failed: ${response.status}`)
  }

  const raw = RawHairAssetIndexResponseSchema.parse(
    (await response.json()) as unknown,
  )

  return {
    code: raw.code,
    message: raw.message,
    hairId: raw.hair_id,
    datasetCode: raw.dataset_code,
    assetBundleSchemaVersion: raw.asset_bundle_schema_version,
    items: raw.items.map(normalizeHairAssetIndexBundle),
  }
}

export function getOrCreateDeviceId() {
  if (typeof window === 'undefined') {
    return 'server-device'
  }

  const stored = window.localStorage.getItem(DEVICE_ID_STORAGE_KEY)
  if (stored) {
    return stored
  }

  const created = window.crypto?.randomUUID?.() ?? `device-${Date.now()}`
  window.localStorage.setItem(DEVICE_ID_STORAGE_KEY, created)
  return created
}

async function postHairApplyV2(
  path: '/home/hairapplybootstrap' | '/home/hairapplyresume',
  payload: Record<string, unknown>,
) {
  const accessToken = getStoredAccessToken()
  const response = await fetch(buildApiUrl(path), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    credentials: 'include',
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let message = '실시간 헤어 적용 세션을 시작하지 못했습니다.'

    try {
      const json = (await response.json()) as { message?: string }
      if (json.message) {
        message = json.message
      }
    } catch {}

    throw new Error(message)
  }

  return normalizeBootstrap(
    RawHairApplyV2ResponseSchema.parse((await response.json()) as unknown),
  )
}

export async function postHairApplyStartV2(hairId: number, deviceId: string) {
  return postHairApplyV2('/home/hairapplybootstrap', {
    hair_id: hairId,
    device_id: deviceId,
    client_capabilities: {
      feature_schema_version: 2,
      transform_version: 'affine_v1',
    },
  })
}

export async function postHairApplyResumeV2(
  applySessionId: string,
  deviceId: string,
) {
  return postHairApplyV2('/home/hairapplyresume', {
    apply_session_id: applySessionId,
    device_id: deviceId,
  })
}

export function parseInferenceMessage(raw: unknown): InferenceIncomingMessage {
  const connected = RawConnectedMessageSchema.safeParse(raw)
  if (connected.success) {
    return {
      type: 'connected',
      applySessionId: connected.data.apply_session_id,
      nodeId: connected.data.node_id,
      featureSchemaVersion: connected.data.feature_schema_version,
      transformVersion: connected.data.transform_version,
    }
  }

  const processed = RawProcessedMessageSchema.safeParse(raw)
  if (processed.success) {
    return {
      type: 'processed',
      applySessionId: processed.data.apply_session_id,
      acceptedSeq: processed.data.accepted_seq,
      processedSeq: processed.data.processed_seq,
      changed: processed.data.changed,
      queueDepth: processed.data.queue_depth,
      droppedPendingCount: processed.data.dropped_pending_count,
      overloaded: processed.data.overloaded,
      asset: normalizeAsset(processed.data.asset),
    }
  }

  const heartbeatAck = RawHeartbeatAckMessageSchema.safeParse(raw)
  if (heartbeatAck.success) {
    return {
      type: 'heartbeat_ack',
      applySessionId: heartbeatAck.data.apply_session_id,
      tsMs: heartbeatAck.data.ts_ms,
    }
  }

  const error = RawErrorMessageSchema.safeParse(raw)
  if (error.success) {
    return error.data
  }

  throw new Error('unknown inference message')
}

export function buildInferenceFeatureMessage({
  applySessionId,
  hairId,
  featureSchemaVersion,
  transformVersion,
  videoWidth,
  videoHeight,
  landmarks,
  pose,
  seq,
}: {
  applySessionId: string
  hairId: number
  featureSchemaVersion: number
  transformVersion: string
  videoWidth: number
  videoHeight: number
  landmarks: NormalizedLandmark[]
  pose: PoseAngles
  seq: number
}): InferenceFeatureMessage {
  const anchors = buildFaceAnchorPoints(landmarks, videoWidth, videoHeight)
  const faceBBox = buildFaceBoundingBox(landmarks, videoWidth, videoHeight)

  return {
    type: 'feature',
    feature_schema_version: featureSchemaVersion,
    coordinate_space: 'pixel_v1',
    anchor_set: 'face_anchor_v1',
    transform_version: transformVersion,
    seq,
    ts_ms: Date.now(),
    apply_session_id: applySessionId,
    hair_id: hairId,
    image_size: {
      width: videoWidth,
      height: videoHeight,
    },
    pose: {
      yaw_float: pose.yaw,
      pitch_float: pose.pitch,
      roll_float: pose.roll,
      yaw_1deg: Math.round(pose.yaw),
      pitch_1deg: Math.round(pose.pitch),
      roll_1deg: Math.round(pose.roll),
    },
    face_bbox: faceBBox,
    anchors,
  }
}
