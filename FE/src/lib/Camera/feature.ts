import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import type { Point3, UserFeatureMessage } from '@/lib/Camera/contracts'
import { getHeadPoseFromMatrix } from '@/lib/Camera/pose'
import type { PoseAngles } from '@/lib/Camera/types'

export type BuildUserFeaturePayloadArgs = {
  hairID: number
  videoWidth: number
  videoHeight: number
  landmarks: NormalizedLandmark[]
  matrixData?: ArrayLike<number> | null
  pose?: PoseAngles | null
  yawSign?: number
  foreheadIndex?: number
  userId?: string
  frameId?: number
  requestId?: string
}

function toPoint3(landmark: NormalizedLandmark): Point3 {
  return {
    x: landmark.x,
    y: landmark.y,
    z: landmark.z ?? 0,
  }
}

export function buildUserFeaturePayload({
  hairID,
  videoWidth,
  videoHeight,
  landmarks,
  matrixData,
  pose,
  yawSign = 1,
  foreheadIndex = 10,
  userId,
  frameId,
  requestId,
}: BuildUserFeaturePayloadArgs): UserFeatureMessage {
  const resolvedPose =
    pose ?? (matrixData ? getHeadPoseFromMatrix(matrixData, yawSign) : null)

  if (!resolvedPose) {
    throw new Error('pose or matrixData is required')
  }

  if (!landmarks[foreheadIndex]) {
    throw new Error(`missing forehead landmark at index ${foreheadIndex}`)
  }

  return {
    type: 'feature',
    hairID,
    userId,
    frameId,
    requestId,
    camera: {
      w: videoWidth,
      h: videoHeight,
    },
    angle: {
      yaw: resolvedPose.yaw,
      pitch: resolvedPose.pitch,
      roll: resolvedPose.roll,
    },
    forehead: toPoint3(landmarks[foreheadIndex]),
    landmark: landmarks.map(toPoint3),
    capturedAt: new Date().toISOString(),
  }
}
