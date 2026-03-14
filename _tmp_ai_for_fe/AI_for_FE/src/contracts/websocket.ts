import { z } from 'zod'

export const Point3Schema = z.object({
  x: z.number(),
  y: z.number(),
  z: z.number(),
})

export const UserFeatureMessageSchema = z.object({
  type: z.literal('feature'),
  hairID: z.number().int().positive(),
  userId: z.string().optional(),
  frameId: z.number().int().nonnegative().optional(),
  requestId: z.string().optional(),
  camera: z.object({
    w: z.number().int().positive(),
    h: z.number().int().positive(),
  }),
  angle: z.object({
    yaw: z.number(),
    pitch: z.number(),
    roll: z.number(),
  }),
  forehead: Point3Schema,
  landmark: z.array(Point3Schema),
  capturedAt: z.string().optional(),
})

export const RecommendationMessageSchema = z.object({
  type: z.literal('recommendation'),
  hairID: z.number().int().positive(),
  assetID: z.string(),
  hairRgbaUrl: z.string(),
  hairRgbaBBox: z
    .object({
      x: z.number().int(),
      y: z.number().int(),
      w: z.number().int(),
      h: z.number().int(),
    })
    .nullable(),
  anchorsUrl: z.string().nullable(),
  matrix: z
    .object({
      m00: z.number(),
      m01: z.number(),
      m02: z.number(),
      m10: z.number(),
      m11: z.number(),
      m12: z.number(),
    })
    .optional(),
})

export const HairApplyWsClientMessageSchema = z.object({
  type: z.enum(['ping', 'status', 'subscribe']).optional(),
  accessToken: z.string().optional(),
  applySessionId: z.string().optional(),
})

const HairApplyStatusDataSchema = z.object({
  code: z.number().int(),
  message: z.string(),
  applySessionId: z.string(),
  jobType: z.string(),
  status: z.string(),
  hairID: z.number().int().optional(),
  completedAt: z.string().nullable().optional(),
})

const HairApplyConnectionDataSchema = z.object({
  endpoint: z.string(),
})

export const HairApplyConnectedMessageSchema = z.object({
  type: z.literal('connected').optional(),
  message: z.string().optional(),
  code: z.number().int().optional(),
  data: HairApplyConnectionDataSchema.optional(),
})

export const HairApplyPongMessageSchema = z.object({
  type: z.literal('pong').optional(),
  message: z.string().optional(),
  code: z.number().int().optional(),
  data: z.null().optional(),
})

export const HairApplyStatusMessageSchema = z.object({
  type: z.literal('status').optional(),
  message: z.string().optional(),
  code: z.number().int().optional(),
  data: HairApplyStatusDataSchema,
})

export const HairApplyErrorMessageSchema = z.object({
  type: z.literal('error').optional(),
  message: z.string().optional(),
  code: z.number().int().optional(),
  data: z.null().optional(),
})

export const HairApplyWsServerMessageSchema = z.union([
  HairApplyConnectedMessageSchema,
  HairApplyPongMessageSchema,
  HairApplyStatusMessageSchema,
  HairApplyErrorMessageSchema,
])

export type Point3 = z.infer<typeof Point3Schema>
export type UserFeatureMessage = z.infer<typeof UserFeatureMessageSchema>
export type RecommendationMessage = z.infer<typeof RecommendationMessageSchema>
export type HairApplyWsClientMessage = z.infer<typeof HairApplyWsClientMessageSchema>
export type HairApplyWsServerMessage = z.infer<typeof HairApplyWsServerMessageSchema>
