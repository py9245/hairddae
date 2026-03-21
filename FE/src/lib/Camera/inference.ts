import { z } from 'zod'

import { buildApiUrl } from '@/lib/api'

const DEVICE_ID_STORAGE_KEY = 'hairapply-device-id'

const IceServerSchema = z.object({
  urls: z.array(z.string()),
  username: z.string().nullable().optional(),
  credential: z.string().nullable().optional(),
})

const RawHairApplyV2ResponseSchema = z
  .object({
    code: z.number().int(),
    message: z.string(),
    success: z.boolean(),
    apply_session_id: z.string(),
    rtc: z.object({
      enabled: z.boolean(),
      offer_url: z.string(),
      connect_ticket: z.string(),
      expires_at: z.string(),
      ice_servers: z.array(IceServerSchema),
    }),
  })
  .passthrough()

const RawConnectedMessageSchema = z
  .object({
    type: z.literal('connected'),
    apply_session_id: z.string().optional(),
    node_id: z.string().optional(),
  })
  .passthrough()

const RawHairAppliedMessageSchema = z.object({
  type: z.literal('hair_applied'),
  hair_id: z.number().int(),
  server_ts_ms: z.number().int().optional(),
})

const RawHeartbeatAckMessageSchema = z.object({
  type: z.literal('heartbeat_ack'),
  ts_ms: z.number().int(),
})

const RawStatsMessageSchema = z.object({
  type: z.literal('stats'),
  queue_depth: z.number().int().optional(),
  dropped_pending_count: z.number().int().optional(),
  decode_ms: z.number().optional(),
  infer_ms: z.number().optional(),
  render_ms: z.number().optional(),
  encode_ms: z.number().optional(),
  e2e_estimate_ms: z.number().optional(),
})

const RawErrorMessageSchema = z.object({
  type: z.literal('error'),
  code: z.string().or(z.number().int()),
  message: z.string(),
})

export type HairApplyV2Response = {
  code: number
  message: string
  success: boolean
  applySessionId: string
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
}

export type RtcOfferResponse = {
  sdp: string
  type: RTCSdpType
}

export type InferenceConnectedMessage = {
  type: 'connected'
  applySessionId: string | null
  nodeId: string | null
}

export type InferenceHairAppliedMessage = {
  type: 'hair_applied'
  hairId: number
  serverTsMs: number | null
}

export type InferenceHeartbeatAckMessage = {
  type: 'heartbeat_ack'
  tsMs: number
}

export type InferenceStatsMessage = {
  type: 'stats'
  queueDepth: number
  droppedPendingCount: number
  decodeMs: number | null
  inferMs: number | null
  renderMs: number | null
  encodeMs: number | null
  e2eEstimateMs: number | null
}

export type InferenceErrorMessage = {
  type: 'error'
  code: string
  message: string
}

export type InferenceControlMessage =
  | InferenceConnectedMessage
  | InferenceHairAppliedMessage
  | InferenceHeartbeatAckMessage
  | InferenceStatsMessage
  | InferenceErrorMessage

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
  const response = await fetch(buildApiUrl(path), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
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

export function safeParseInferenceControlMessage(
  raw: unknown,
): InferenceControlMessage | null {
  const connected = RawConnectedMessageSchema.safeParse(raw)
  if (connected.success) {
    return {
      type: 'connected',
      applySessionId: connected.data.apply_session_id ?? null,
      nodeId: connected.data.node_id ?? null,
    }
  }

  const hairApplied = RawHairAppliedMessageSchema.safeParse(raw)
  if (hairApplied.success) {
    return {
      type: 'hair_applied',
      hairId: hairApplied.data.hair_id,
      serverTsMs: hairApplied.data.server_ts_ms ?? null,
    }
  }

  const heartbeatAck = RawHeartbeatAckMessageSchema.safeParse(raw)
  if (heartbeatAck.success) {
    return {
      type: 'heartbeat_ack',
      tsMs: heartbeatAck.data.ts_ms,
    }
  }

  const stats = RawStatsMessageSchema.safeParse(raw)
  if (stats.success) {
    return {
      type: 'stats',
      queueDepth: stats.data.queue_depth ?? 0,
      droppedPendingCount: stats.data.dropped_pending_count ?? 0,
      decodeMs: stats.data.decode_ms ?? null,
      inferMs: stats.data.infer_ms ?? null,
      renderMs: stats.data.render_ms ?? null,
      encodeMs: stats.data.encode_ms ?? null,
      e2eEstimateMs: stats.data.e2e_estimate_ms ?? null,
    }
  }

  const error = RawErrorMessageSchema.safeParse(raw)
  if (error.success) {
    return {
      type: 'error',
      code: String(error.data.code),
      message: error.data.message,
    }
  }

  return null
}
