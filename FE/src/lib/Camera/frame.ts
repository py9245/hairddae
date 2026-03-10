import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import type { FaceFrame } from '@/lib/Camera/types'

export function updateFrameRef(
  frameRef: React.RefObject<FaceFrame | null> | undefined,
  now: number,
  w: number,
  h: number,
  lms: NormalizedLandmark[] | null,
  pose: FaceFrame['pose'],
) {
  if (!frameRef) return

  frameRef.current = {
    t: now,
    videoW: w,
    videoH: h,
    faceFound: !!lms,
    landmarks: lms ?? [],
    pose,
  }
}
