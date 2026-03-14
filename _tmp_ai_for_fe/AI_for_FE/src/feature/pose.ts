import * as THREE from 'three'

export type PoseAngles = {
  yaw: number
  pitch: number
  roll: number
}

const mat4 = new THREE.Matrix4()
const euler = new THREE.Euler()

function radToDeg(value: number) {
  return (value * 180) / Math.PI
}

export function getHeadPoseFromMatrix(
  matrixData: ArrayLike<number>,
  yawSign = 1,
): PoseAngles {
  mat4.fromArray(Array.from(matrixData))
  euler.setFromRotationMatrix(mat4)

  return {
    pitch: radToDeg(euler.x),
    yaw: radToDeg(euler.y) * yawSign,
    roll: radToDeg(euler.z),
  }
}

export function roundPoseAngles(pose: PoseAngles) {
  return {
    yaw1deg: Math.round(pose.yaw),
    pitch1deg: Math.round(pose.pitch),
    roll1deg: Math.round(pose.roll),
  }
}
