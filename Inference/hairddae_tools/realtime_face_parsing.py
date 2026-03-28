from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image
import torchvision.transforms as transforms

from cv2_cuda_utils import opencv_bitwise_and, opencv_bitwise_not, opencv_cvt_color, opencv_dilate, opencv_gaussian_blur, opencv_resize
from extract_asset_parsing_masks import (
    binary_mask,
    build_soft_alpha,
    build_soft_alpha_with_suppression,
    build_overlap_suppression_mask,
    compute_forehead_mask,
    dilate,
    expanded_head_roi,
    refine_hair_mask,
)
from local_demo_paths import default_face_parsing_repo_dir, default_face_parsing_weights


def _preferred_device(device_name: str | None) -> torch.device:
    if device_name:
        requested = str(device_name).strip().lower()
        if requested.startswith("cuda") and torch.cuda.is_available():
            return torch.device(requested)
        if requested == "cpu":
            return torch.device("cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _mask_ratio(mask: np.ndarray) -> float:
    return float(np.count_nonzero(mask)) / float(mask.shape[0] * mask.shape[1])


def _build_blur_mask(
    hair_mask: np.ndarray,
    protect_face_mask: np.ndarray,
    ear_left_mask: np.ndarray,
    ear_right_mask: np.ndarray,
    face_bbox: dict[str, Any] | None,
) -> np.ndarray:
    if hair_mask.size == 0 or np.count_nonzero(hair_mask) <= 0:
        return np.zeros_like(hair_mask, dtype=np.uint8)

    face_width = max(1.0, float((face_bbox or {}).get("w") or 0.0))
    grow_radius = max(11, int(round(face_width * 0.10)))
    protect_radius = max(5, int(round(face_width * 0.03)))

    expanded_hair = dilate(hair_mask, grow_radius)
    protect = np.maximum(protect_face_mask, np.maximum(ear_left_mask, ear_right_mask))
    softened_protect = dilate(protect, protect_radius)
    blur_region = cv2.bitwise_and(expanded_hair, cv2.bitwise_not(softened_protect))
    sigma = max(5.0, face_width * 0.05)
    softened = opencv_gaussian_blur(blur_region, (0, 0), sigma_x=sigma, sigma_y=sigma, min_pixels=24_000)
    return np.clip(softened, 0, 255).astype(np.uint8)


class RuntimeFaceParsing:
    def __init__(
        self,
        repo_dir: str | Path | None = None,
        weights: str | Path | None = None,
        device: str | None = None,
    ) -> None:
        self.repo_dir = Path(repo_dir).expanduser().resolve() if repo_dir else default_face_parsing_repo_dir()
        self.weights = Path(weights).expanduser().resolve() if weights else default_face_parsing_weights()
        self.device = _preferred_device(device)
        self.ready = False

        if str(self.repo_dir) not in sys.path:
            sys.path.insert(0, str(self.repo_dir))
        from model import BiSeNet  # type: ignore

        self.net = BiSeNet(n_classes=19)
        state = torch.load(self.weights, map_location=self.device)
        self.net.load_state_dict(state)
        self.net.to(self.device)
        self.net.eval()
        self.to_tensor = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
            ]
        )
        self.label_skin = {1}
        self.label_ears_l = {7}
        self.label_ears_r = {8}
        self.label_face_core = {1, 2, 3, 4, 5, 6, 10, 11, 12, 13}
        self.label_neck = {14, 15, 16}
        self.label_hair = {17, 18}
        self.ready = True

    def parse_frame(
        self,
        frame_bgr: np.ndarray,
        user_row: dict[str, Any],
    ) -> dict[str, Any] | None:
        if frame_bgr is None or frame_bgr.size == 0:
            return None
        face_bbox = user_row.get("face_bbox") or {}
        anchors = user_row.get("anchors") or {}
        if not face_bbox or not face_bbox.get("w") or not face_bbox.get("h"):
            return None
        if not anchors:
            return None

        height, width = frame_bgr.shape[:2]
        x0, y0, roi_w, roi_h = expanded_head_roi(face_bbox, width, height)
        if roi_w <= 0 or roi_h <= 0:
            return None
        roi_bgr = frame_bgr[y0 : y0 + roi_h, x0 : x0 + roi_w]
        if roi_bgr.size == 0:
            return None

        roi_rgb = opencv_cvt_color(roi_bgr, cv2.COLOR_BGR2RGB, min_pixels=8_192)
        pil_image = Image.fromarray(roi_rgb).resize((512, 512), Image.BILINEAR)
        tensor = self.to_tensor(pil_image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            out = self.net(tensor)[0]
            parsing_512 = out.argmax(1)[0].cpu().numpy().astype(np.uint8)
            hair_confidence_512 = torch.softmax(out, dim=1)[:, 17:19].sum(dim=1)[0].cpu().numpy().astype(np.float32)

        parsing_roi = opencv_resize(parsing_512, (roi_w, roi_h), interpolation=cv2.INTER_NEAREST, min_pixels=8_192)
        hair_confidence_roi = opencv_resize(hair_confidence_512, (roi_w, roi_h), interpolation=cv2.INTER_LINEAR, min_pixels=8_192)

        parsing = np.zeros((height, width), dtype=np.uint8)
        hair_confidence = np.zeros((height, width), dtype=np.float32)
        parsing[y0 : y0 + roi_h, x0 : x0 + roi_w] = parsing_roi
        hair_confidence[y0 : y0 + roi_h, x0 : x0 + roi_w] = hair_confidence_roi

        hair_mask = binary_mask(parsing, self.label_hair)
        skin_mask = binary_mask(parsing, self.label_skin)
        face_mask = binary_mask(parsing, self.label_face_core)
        ear_left_mask = binary_mask(parsing, self.label_ears_l)
        ear_right_mask = binary_mask(parsing, self.label_ears_r)
        neck_shoulder_mask = binary_mask(parsing, self.label_neck)
        hair_mask = refine_hair_mask(
            hair_mask,
            face_mask,
            ear_left_mask,
            ear_right_mask,
            neck_shoulder_mask,
            anchors,
            face_bbox,
        )
        forehead_mask = compute_forehead_mask(skin_mask, face_bbox, anchors)
        protect_face_mask = np.maximum(dilate(face_mask, 9), dilate(cv2.bitwise_or(ear_left_mask, ear_right_mask), 5))
        head_silhouette_mask = np.maximum(
            dilate(hair_mask, 7),
            np.maximum(
                dilate(protect_face_mask, 3),
                dilate(forehead_mask, 5),
            ),
        )
        overlap_suppression = build_overlap_suppression_mask(
            face_mask=face_mask,
            ear_left=ear_left_mask,
            ear_right=ear_right_mask,
            anchors=anchors,
            face_bbox=face_bbox,
        )
        suppress_prior_mask = np.maximum(
            opencv_bitwise_and(dilate(hair_mask, 11), opencv_bitwise_not(protect_face_mask)),
            overlap_suppression,
        )
        alpha_mask = build_soft_alpha_with_suppression(hair_mask, hair_confidence, suppress_prior_mask)
        blur_mask = _build_blur_mask(
            hair_mask,
            protect_face_mask,
            ear_left_mask,
            ear_right_mask,
            face_bbox,
        )

        return {
            "parsing": parsing,
            "hair_confidence": hair_confidence,
            "hair_mask": hair_mask,
            "face_mask": face_mask,
            "forehead_mask": forehead_mask,
            "ear_left_mask": ear_left_mask,
            "ear_right_mask": ear_right_mask,
            "neck_shoulder_mask": neck_shoulder_mask,
            "protect_face_mask": protect_face_mask,
            "head_silhouette_mask": head_silhouette_mask,
            "suppress_prior_mask": suppress_prior_mask,
            "alpha_mask": alpha_mask,
            "blur_mask": blur_mask,
            "roi": {"x": x0, "y": y0, "w": roi_w, "h": roi_h},
            "metrics": {
                "hair_area_ratio": round(_mask_ratio(hair_mask), 6),
                "face_area_ratio": round(_mask_ratio(face_mask), 6),
                "blur_area_ratio": round(_mask_ratio(blur_mask), 6),
            },
        }
