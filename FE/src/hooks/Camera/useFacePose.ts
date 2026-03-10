import { useMemo } from 'react'
import type { DetectForVideoResult } from '@/hooks/Camera/useFaceLandmarkersLoop'
import { getHeadPoseFromMatrix } from '@/lib/Camera/pose'

type PoseLike = {
  pitch?: number
  yaw?: number
  roll?: number
  x?: number
  y?: number
  z?: number
}

export type PoseNorm = { x: number; y: number; z: number } | null

function normDeg0to359(deg: number) {
  const d = ((deg % 360) + 360) % 360
  return Math.round(d)
}

export function useFacePose({
  result,
  yawSign = 1,
}: {
  result: DetectForVideoResult | null
  yawSign?: number
}) {
  return useMemo(() => {
    const ftm = result?.facialTransformationMatrixes?.[0]?.data
    const pose = ftm ? getHeadPoseFromMatrix(ftm, yawSign) : null

    let poseNorm: PoseNorm = null

    if (pose) {
      const poseValue = pose as PoseLike
      const x = poseValue.pitch ?? poseValue.x ?? 0
      const y = poseValue.yaw ?? poseValue.y ?? 0
      const z = poseValue.roll ?? poseValue.z ?? 0

      poseNorm = {
        x: normDeg0to359(x),
        y: normDeg0to359(y),
        z: normDeg0to359(z),
      }
    }

    return { ftm, pose, poseNorm }
  }, [result, yawSign])
}
