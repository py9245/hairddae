from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")
pytest.importorskip("mediapipe")
pytest.importorskip("torch")
pytest.importorskip("torchvision")

from app.face_tracking import FACE_LANDMARK_INDEX
from app.hair_attenuation import HairAttenuator


def _build_landmarks() -> np.ndarray:
    landmarks = np.zeros((478, 2), dtype=np.int32)
    landmarks[FACE_LANDMARK_INDEX["forehead_top"]] = (96, 44)
    landmarks[FACE_LANDMARK_INDEX["forehead_mid"]] = (96, 60)
    landmarks[FACE_LANDMARK_INDEX["left_temple"]] = (58, 72)
    landmarks[FACE_LANDMARK_INDEX["right_temple"]] = (134, 72)
    landmarks[FACE_LANDMARK_INDEX["left_ear_root"]] = (44, 108)
    landmarks[FACE_LANDMARK_INDEX["right_ear_root"]] = (148, 108)
    landmarks[FACE_LANDMARK_INDEX["left_side"]] = (56, 126)
    landmarks[FACE_LANDMARK_INDEX["right_side"]] = (136, 126)
    landmarks[FACE_LANDMARK_INDEX["lower_left"]] = (68, 176)
    landmarks[FACE_LANDMARK_INDEX["lower_right"]] = (124, 176)
    landmarks[FACE_LANDMARK_INDEX["chin_center"]] = (96, 196)
    return landmarks


def test_hair_attenuation_softens_upper_hair_roi() -> None:
    frame = np.full((256, 192, 3), 35, dtype=np.uint8)
    frame[10:120, 28:164] = np.array([15, 40, 170], dtype=np.uint8)
    frame[96:240, 48:144] = np.array([120, 165, 210], dtype=np.uint8)
    landmarks = _build_landmarks()

    attenuator = HairAttenuator()
    output = attenuator.apply(frame, landmarks)

    assert output.shape == frame.shape
    assert output.dtype == np.uint8
    assert not np.array_equal(output, frame)

    hair_delta = np.abs(output[20:110, 36:156].astype(np.int16) - frame[20:110, 36:156].astype(np.int16)).mean()
    face_delta = np.abs(output[120:220, 64:128].astype(np.int16) - frame[120:220, 64:128].astype(np.int16)).mean()
    assert hair_delta > 6.0
    assert face_delta < hair_delta


def test_hair_attenuation_returns_hair_tone_metadata() -> None:
    frame = np.full((256, 192, 3), 24, dtype=np.uint8)
    frame[14:120, 28:164] = np.array([28, 52, 88], dtype=np.uint8)
    frame[96:240, 48:144] = np.array([145, 175, 210], dtype=np.uint8)
    landmarks = _build_landmarks()

    attenuator = HairAttenuator()
    output, metadata = attenuator.apply_with_metadata(frame, landmarks)

    assert output.shape == frame.shape
    assert metadata["mean_luma"] > 30.0
    assert 0.02 < metadata["coverage"] <= 1.0
    assert metadata["mask_kind"] == "landmark"


def test_hair_attenuation_segmentation_mask_applies_zone_suppression() -> None:
    background = np.array([42, 56, 68], dtype=np.uint8)
    frame = np.full((256, 192, 3), background, dtype=np.uint8)
    frame[8:128, 24:168] = np.array([26, 44, 92], dtype=np.uint8)
    frame[64:136, 60:132] = np.array([164, 188, 214], dtype=np.uint8)
    frame[148:248, 6:48] = np.array([18, 34, 96], dtype=np.uint8)
    landmarks = _build_landmarks()
    hair_confidence_mask = np.zeros((256, 192), dtype=np.float32)
    hair_confidence_mask[8:128, 24:168] = 0.96
    hair_confidence_mask[148:248, 6:48] = 0.96
    hair_confidence_mask[24:72, 24:54] = 0.0

    attenuator = HairAttenuator(segmentation_confidence_threshold=0.25, strength=0.92)
    output, metadata = attenuator.apply_with_metadata(
        frame,
        landmarks,
        user_row={},
        hair_confidence_mask=hair_confidence_mask,
    )

    assert metadata["mask_kind"] == "segmentation_full"
    assert metadata["suppression_mode"] == "segmentation_zones"
    assert metadata["covered_mode"] == "scalp_matte_only"
    hole_original = frame[28:60, 28:50].astype(np.float32).mean(axis=(0, 1))
    hole_output = output[28:60, 28:50].astype(np.float32).mean(axis=(0, 1))
    fringe_original = frame[44:68, 78:114].astype(np.float32).mean(axis=(0, 1))
    fringe_output = output[44:68, 78:114].astype(np.float32).mean(axis=(0, 1))
    skin_color = frame[78:122, 72:120].astype(np.float32).mean(axis=(0, 1))
    scalp_color = np.asarray(metadata["scalp_color"], dtype=np.float32)
    bulk_original = frame[184:236, 10:40].astype(np.float32).mean(axis=(0, 1))
    bulk_output = output[184:236, 10:40].astype(np.float32).mean(axis=(0, 1))
    background_color = frame[180:236, 52:92].astype(np.float32).mean(axis=(0, 1))

    assert float(np.abs(hole_output - hole_original).mean()) < 3.0
    assert float(np.abs(fringe_output - skin_color).mean()) < float(np.abs(fringe_original - skin_color).mean())
    assert float(np.abs(fringe_output - scalp_color).mean()) < float(np.abs(fringe_original - scalp_color).mean())
    assert float(np.abs(bulk_output - background_color).mean()) < float(np.abs(bulk_original - background_color).mean())


def test_hair_attenuation_segmentation_feathers_hairline_boundary() -> None:
    frame = np.full((256, 192, 3), 38, dtype=np.uint8)
    frame[8:120, 24:168] = np.array([24, 40, 88], dtype=np.uint8)
    frame[120:244, 44:148] = np.array([164, 188, 214], dtype=np.uint8)
    landmarks = _build_landmarks()
    hair_confidence_mask = np.zeros((256, 192), dtype=np.float32)
    hair_confidence_mask[8:120, 24:168] = 0.96

    attenuator = HairAttenuator(segmentation_confidence_threshold=0.25, strength=0.92)
    output, metadata = attenuator.apply_with_metadata(
        frame,
        landmarks,
        user_row={},
        hair_confidence_mask=hair_confidence_mask,
    )

    scalp_color = np.asarray(metadata["scalp_color"], dtype=np.float32)
    inner_original = frame[36:60, 76:116].astype(np.float32).mean(axis=(0, 1))
    inner_output = output[36:60, 76:116].astype(np.float32).mean(axis=(0, 1))
    edge_original = frame[102:116, 76:116].astype(np.float32).mean(axis=(0, 1))
    edge_output = output[102:116, 76:116].astype(np.float32).mean(axis=(0, 1))

    assert metadata["boundary_feather_px"] >= 4
    assert float(np.abs(inner_output - scalp_color).mean()) < float(np.abs(inner_original - scalp_color).mean())
    assert float(np.abs(edge_output - edge_original).mean()) < float(np.abs(inner_output - inner_original).mean())
    assert float(np.abs(edge_output - scalp_color).mean()) > float(np.abs(inner_output - scalp_color).mean())


def test_hair_attenuation_bald_test_mode_stays_within_segmentation_mask() -> None:
    background = np.array([214, 216, 222], dtype=np.uint8)
    skin = np.array([156, 182, 210], dtype=np.uint8)
    hair = np.array([34, 42, 70], dtype=np.uint8)
    frame = np.full((256, 192, 3), background, dtype=np.uint8)
    frame[8:140, 20:172] = hair
    frame[56:220, 56:136] = skin
    landmarks = _build_landmarks()
    hair_confidence_mask = np.zeros((256, 192), dtype=np.float32)
    hair_confidence_mask[12:136, 24:168] = 0.96
    hair_confidence_mask[40:72, 82:112] = 0.0

    attenuator = HairAttenuator(
        segmentation_confidence_threshold=0.25,
        strength=0.92,
        bald_test_mode=True,
    )
    output, metadata = attenuator.apply_with_metadata(
        frame,
        landmarks,
        user_row={},
        hair_confidence_mask=hair_confidence_mask,
    )

    assert metadata["suppression_mode"] == "bald_test_segmentation_only"
    changed_original = frame[20:52, 40:76].astype(np.float32).mean(axis=(0, 1))
    changed_output = output[20:52, 40:76].astype(np.float32).mean(axis=(0, 1))
    skin_color = frame[88:122, 72:120].astype(np.float32).mean(axis=(0, 1))
    hole_original = frame[48:68, 84:110].astype(np.float32).mean(axis=(0, 1))
    hole_output = output[48:68, 84:110].astype(np.float32).mean(axis=(0, 1))
    changed_original_luma = float(changed_original.mean())
    changed_output_luma = float(changed_output.mean())

    assert float(np.abs(changed_output - skin_color).mean()) < float(np.abs(changed_original - skin_color).mean())
    assert changed_output_luma > changed_original_luma
    assert float(np.abs(hole_output - hole_original).mean()) < 12.0
    outside_original = frame[8:18, 12:22].astype(np.float32).mean(axis=(0, 1))
    outside_output = output[8:18, 12:22].astype(np.float32).mean(axis=(0, 1))
    assert float(np.abs(outside_output - outside_original).mean()) < 1.0
