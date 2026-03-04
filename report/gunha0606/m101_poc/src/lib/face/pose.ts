// lib/face/pose.ts
import * as THREE from "three";
import type { PoseAngles, PoseStatus } from "@/lib/face/types";

function radToDeg(r: number) {
  return (r * 180) / Math.PI;
}

const _mat4 = new THREE.Matrix4();
const _euler = new THREE.Euler();

export function getHeadPoseFromMatrix(
  matrixData: ArrayLike<number>,
  yawSign = 1
): PoseAngles {
  _mat4.fromArray(matrixData as number[]);
  _euler.setFromRotationMatrix(_mat4);

  return {
    pitch: radToDeg(_euler.x),
    yaw: radToDeg(_euler.y) * yawSign,
    roll: radToDeg(_euler.z),
  };
}

export function classifyPose(p: PoseAngles): PoseStatus {
  const { yaw, pitch, roll } = p;

  const FRONT =
    Math.abs(yaw) < 12 && Math.abs(pitch) < 12 && Math.abs(roll) < 15;
  if (FRONT) return "front";

  const SIDE_OK = Math.abs(pitch) < 20 && Math.abs(roll) < 25;

  if (SIDE_OK && yaw > 30 && yaw < 95) return "right";
  if (SIDE_OK && yaw < -30 && yaw > -95) return "left";

  return "none";
}