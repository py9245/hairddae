import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import type { Point3, UserFeatureMessage } from '@/contracts/websocket'
import { getHeadPoseFromMatrix, type PoseAngles } from '@/feature/pose'

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

export function toPoint3(landmark: NormalizedLandmark): Point3 {
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
    throw new Error('pose 또는 matrixData 중 하나는 필요합니다.')
  }

  if (!landmarks[foreheadIndex]) {
    throw new Error(`forehead index ${foreheadIndex} landmark가 없습니다.`)
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
