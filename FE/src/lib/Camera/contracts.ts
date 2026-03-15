import { z } from 'zod'

export const Point3Schema = z.object({
  x: z.number(),
  y: z.number(),
  z: z.number(),
})

export const UserFeatureMessageSchema = z.object({
  type: z.literal('feature'),
  hairID: z.number().int().nonnegative(),
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

export type Point3 = z.infer<typeof Point3Schema>
export type UserFeatureMessage = z.infer<typeof UserFeatureMessageSchema>
