// lib/segmentation/hairSegmenter.ts
import { FilesetResolver, ImageSegmenter } from "@mediapipe/tasks-vision";

let seg: ImageSegmenter | null = null;

export async function initHairSegmenter(modelPath = "/models/hair_segmenter.tflite") {
  if (seg) return seg;

  const vision = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm"
  );

  seg = await ImageSegmenter.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: modelPath,
      delegate: "GPU", // 느리면 "CPU"
    },
    runningMode: "VIDEO",
    outputCategoryMask: true,
    outputConfidenceMasks: false,
  });

  return seg;
}

export function getHairSegmenter() {
  return seg;
}