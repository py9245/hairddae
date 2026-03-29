from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")
pytest.importorskip("mediapipe")
pytest.importorskip("torch")
pytest.importorskip("torchvision")

from app.face_tracking import FACE_LANDMARK_INDEX
from app.hair_attenuation import HairAttenuator


LEFT_EYE_TEST_POINTS = {
    33: (70, 110),
    246: (73, 106),
    161: (78, 104),
    160: (82, 104),
    159: (86, 105),
    158: (89, 108),
    157: (90, 110),
    173: (88, 112),
    133: (84, 114),
    155: (80, 116),
    154: (76, 116),
    153: (72, 115),
    145: (69, 113),
    144: (68, 111),
    163: (69, 109),
    7: (70, 108),
}
RIGHT_EYE_TEST_POINTS = {
    263: (122, 110),
    466: (119, 106),
    388: (114, 104),
    387: (110, 104),
    386: (106, 105),
    385: (103, 108),
    384: (102, 110),
    398: (104, 112),
    362: (108, 114),
    382: (112, 116),
    381: (116, 116),
    380: (120, 115),
    374: (123, 113),
    373: (124, 111),
    390: (123, 109),
    249: (122, 108),
}


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
    for index, point in LEFT_EYE_TEST_POINTS.items():
        landmarks[index] = point
    for index, point in RIGHT_EYE_TEST_POINTS.items():
        landmarks[index] = point
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
    fringe_original = frame[44:68, 78:114].astype(np.float32).mean(axis=(0, 1))
    fringe_output = output[44:68, 78:114].astype(np.float32).mean(axis=(0, 1))
    skin_color = frame[78:122, 72:120].astype(np.float32).mean(axis=(0, 1))
    scalp_color = np.asarray(metadata["scalp_color"], dtype=np.float32)
    bulk_original = frame[184:236, 10:40].astype(np.float32).mean(axis=(0, 1))
    bulk_output = output[184:236, 10:40].astype(np.float32).mean(axis=(0, 1))
    background_color = frame[180:236, 52:92].astype(np.float32).mean(axis=(0, 1))
    far_background_original = frame[196:236, 146:182].astype(np.float32).mean(axis=(0, 1))
    far_background_output = output[196:236, 146:182].astype(np.float32).mean(axis=(0, 1))

    assert float(np.abs(fringe_output - skin_color).mean()) < float(np.abs(fringe_original - skin_color).mean())
    assert float(np.abs(fringe_output - scalp_color).mean()) < float(np.abs(fringe_original - scalp_color).mean())
    assert float(np.abs(bulk_output - background_color).mean()) < float(np.abs(bulk_original - background_color).mean())
    assert float(np.abs(far_background_output - far_background_original).mean()) < 1.0


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


def test_hair_attenuation_preserves_eye_regions_precisely() -> None:
    frame = np.full((256, 192, 3), 210, dtype=np.uint8)
    frame[8:140, 20:172] = np.array([28, 36, 72], dtype=np.uint8)
    frame[64:220, 44:148] = np.array([170, 196, 222], dtype=np.uint8)
    frame[104:118, 66:92] = np.array([24, 28, 34], dtype=np.uint8)
    frame[104:118, 100:126] = np.array([24, 28, 34], dtype=np.uint8)
    landmarks = _build_landmarks()
    hair_confidence_mask = np.zeros((256, 192), dtype=np.float32)
    hair_confidence_mask[8:140, 20:172] = 0.96

    attenuator = HairAttenuator(
        segmentation_confidence_threshold=0.25,
        strength=0.92,
        preserve_eyes_enabled=True,
    )
    output, _ = attenuator.apply_with_metadata(
        frame,
        landmarks,
        user_row={},
        hair_confidence_mask=hair_confidence_mask,
    )
    baseline_output, _ = HairAttenuator(
        segmentation_confidence_threshold=0.25,
        strength=0.92,
        preserve_eyes_enabled=False,
    ).apply_with_metadata(
        frame,
        landmarks,
        user_row={},
        hair_confidence_mask=hair_confidence_mask,
    )

    left_eye_original = frame[104:118, 66:92].astype(np.float32)
    left_eye_output = output[104:118, 66:92].astype(np.float32)
    left_eye_baseline = baseline_output[104:118, 66:92].astype(np.float32)
    left_eye_delta = float(np.abs(left_eye_output - left_eye_original).mean())
    left_eye_baseline_delta = float(np.abs(left_eye_baseline - left_eye_original).mean())

    assert left_eye_delta < left_eye_baseline_delta


def test_estimate_skin_color_prefers_skin_like_face_patches() -> None:
    frame = np.full((256, 192, 3), np.array([24, 28, 34], dtype=np.uint8), dtype=np.uint8)
    frame[38:112, 34:158] = np.array([20, 24, 32], dtype=np.uint8)
    frame[60:210, 42:150] = np.array([164, 188, 214], dtype=np.uint8)
    frame[56:94, 70:122] = np.array([150, 176, 205], dtype=np.uint8)
    landmarks = _build_landmarks()

    skin_color = HairAttenuator()._estimate_skin_color(frame, landmarks)

    assert skin_color is not None
    skin_reference = frame[96:148, 58:134].astype(np.float32).mean(axis=(0, 1))
    hair_reference = frame[44:88, 48:144].astype(np.float32).mean(axis=(0, 1))
    assert float(np.abs(skin_color - skin_reference).mean()) < float(np.abs(skin_color - hair_reference).mean())


def test_blend_scalp_reference_color_prefers_face_skin_over_dark_boundary() -> None:
    skin = np.array([170.0, 192.0, 214.0], dtype=np.float32)
    boundary = np.array([118.0, 136.0, 160.0], dtype=np.float32)

    blended = HairAttenuator._blend_scalp_reference_color(skin, boundary)

    assert blended is not None
    assert float(np.abs(blended - skin).mean()) < float(np.abs(blended - boundary).mean())


def test_compose_luma_preserving_scalp_matte_keeps_lowfreq_shading() -> None:
    lowfreq = np.full((24, 24, 3), np.array([150, 172, 196], dtype=np.uint8), dtype=np.uint8)
    lowfreq[:12, :, :] = np.array([132, 152, 174], dtype=np.uint8)
    active_region = np.ones((24, 24), dtype=bool)

    matte = HairAttenuator._compose_luma_preserving_scalp_matte(
        lowfreq,
        np.array([164.0, 186.0, 210.0], dtype=np.float32),
        active_region=active_region,
    )

    assert matte.shape == lowfreq.shape
    top_mean = float(matte[:12].mean())
    bottom_mean = float(matte[12:].mean())
    assert bottom_mean > top_mean


def test_forehead_fringe_mask_extends_to_temple_sides() -> None:
    landmarks = _build_landmarks()
    attenuator = HairAttenuator()

    fringe_mask = attenuator._build_forehead_fringe_mask((256, 192, 3), landmarks)

    assert fringe_mask is not None
    assert fringe_mask[48, 64] > 0
    assert fringe_mask[52, 132] > 0
    assert fringe_mask[62, 52] > 0
    assert fringe_mask[62, 140] > 0
    assert fringe_mask[76, 48] > 0
    assert fringe_mask[76, 144] > 0
    assert fringe_mask[84, 40] > 0
    assert fringe_mask[84, 152] > 0
    assert fringe_mask[56, 152] > 0
    assert fringe_mask[92, 52] > 0
    assert fringe_mask[92, 140] > 0
    assert fringe_mask[76, 36] == 0
    assert fringe_mask[76, 156] == 0
    assert fringe_mask[72, 160] == 0
    assert fringe_mask[104, 44] > 0
    assert fringe_mask[104, 148] > 0
    assert fringe_mask[120, 148] == 0
    assert fringe_mask[110, 120] > 0
    assert fringe_mask[118, 120] == 0
    assert fringe_mask[176, 18] == 0


def test_local_boundary_skin_field_supports_crop_relative_boundary_coordinates() -> None:
    attenuator = HairAttenuator()
    frame = np.full((32, 20, 3), np.array([160, 184, 208], dtype=np.uint8), dtype=np.uint8)
    hair_mask = np.zeros((32, 20), dtype=np.uint8)
    fringe_mask = np.zeros((32, 20), dtype=np.uint8)
    active_x = np.array([10, 11, 12, 13], dtype=np.int32)
    smoothed_boundary = np.array([8.0, 8.5, 9.0, 9.5], dtype=np.float32)

    field = attenuator._build_local_boundary_skin_field(
        frame,
        hair_mask,
        fringe_mask,
        landmarks_px=None,
        reference_skin_color=np.array([160.0, 184.0, 208.0], dtype=np.float32),
        active_x=active_x,
        smoothed_boundary=smoothed_boundary,
    )

    assert field is not None
    cols, colors = field
    assert np.array_equal(cols, active_x)
    assert colors.shape == (4, 3)


def test_hair_attenuation_fringe_softens_temple_side_region() -> None:
    background = np.array([42, 56, 68], dtype=np.uint8)
    frame = np.full((256, 192, 3), background, dtype=np.uint8)
    frame[8:128, 24:168] = np.array([24, 40, 88], dtype=np.uint8)
    frame[64:196, 56:136] = np.array([168, 192, 216], dtype=np.uint8)
    landmarks = _build_landmarks()
    hair_confidence_mask = np.zeros((256, 192), dtype=np.float32)
    hair_confidence_mask[8:128, 24:168] = 0.96

    output, _ = HairAttenuator(
        segmentation_confidence_threshold=0.25,
        strength=0.92,
        disable_covered_suppression=True,
    ).apply_with_metadata(
        frame,
        landmarks,
        user_row={},
        hair_confidence_mask=hair_confidence_mask,
    )

    skin_color = frame[82:126, 72:120].astype(np.float32).mean(axis=(0, 1))
    temple_original = frame[78:112, 34:60].astype(np.float32).mean(axis=(0, 1))
    temple_output = output[78:112, 34:60].astype(np.float32).mean(axis=(0, 1))

    assert float(np.abs(temple_output - skin_color).mean()) < float(np.abs(temple_original - skin_color).mean())


def test_hair_attenuation_outer_band_softens_below_fringe_boundary() -> None:
    background = np.array([42, 56, 68], dtype=np.uint8)
    hair = np.array([24, 40, 88], dtype=np.uint8)
    skin = np.array([168, 192, 216], dtype=np.uint8)
    frame = np.full((256, 192, 3), background, dtype=np.uint8)
    frame[8:128, 24:168] = hair
    frame[64:196, 56:136] = skin
    landmarks = _build_landmarks()
    hair_confidence_mask = np.zeros((256, 192), dtype=np.float32)
    hair_confidence_mask[8:128, 24:168] = 0.96

    output, metadata = HairAttenuator(
        segmentation_confidence_threshold=0.25,
        strength=0.92,
        disable_covered_suppression=True,
        disable_outer_bulk_suppression=True,
    ).apply_with_metadata(
        frame,
        landmarks,
        user_row={},
        hair_confidence_mask=hair_confidence_mask,
    )

    band_region_original = frame[92:104, 40:56].astype(np.float32)
    band_region_output = output[92:104, 40:56].astype(np.float32)
    scalp_color = np.asarray(metadata["scalp_color"], dtype=np.float32)

    assert metadata["fringe_mask"][97, 36] == 0
    assert float(np.abs(band_region_output - band_region_original).mean()) > 1.0
    assert float(np.abs(band_region_output.mean(axis=(0, 1)) - scalp_color).mean()) < float(
        np.abs(band_region_original.mean(axis=(0, 1)) - scalp_color).mean()
    )


def test_hair_attenuation_can_disable_outer_bulk_suppression() -> None:
    background = np.array([42, 56, 68], dtype=np.uint8)
    frame = np.full((256, 192, 3), background, dtype=np.uint8)
    frame[8:128, 24:168] = np.array([26, 44, 92], dtype=np.uint8)
    frame[64:136, 60:132] = np.array([164, 188, 214], dtype=np.uint8)
    frame[148:248, 6:48] = np.array([18, 34, 96], dtype=np.uint8)
    landmarks = _build_landmarks()
    hair_confidence_mask = np.zeros((256, 192), dtype=np.float32)
    hair_confidence_mask[8:128, 24:168] = 0.96
    hair_confidence_mask[148:248, 6:48] = 0.96

    output, metadata = HairAttenuator(
        segmentation_confidence_threshold=0.25,
        strength=0.92,
        disable_outer_bulk_suppression=True,
    ).apply_with_metadata(
        frame,
        landmarks,
        user_row={},
        hair_confidence_mask=hair_confidence_mask,
    )
    baseline_output, _ = HairAttenuator(
        segmentation_confidence_threshold=0.25,
        strength=0.92,
        disable_outer_bulk_suppression=False,
    ).apply_with_metadata(
        frame,
        landmarks,
        user_row={},
        hair_confidence_mask=hair_confidence_mask,
    )

    bulk_original = frame[184:236, 10:40].astype(np.float32).mean(axis=(0, 1))
    bulk_output = output[184:236, 10:40].astype(np.float32).mean(axis=(0, 1))
    bulk_baseline = baseline_output[184:236, 10:40].astype(np.float32).mean(axis=(0, 1))

    assert metadata["outer_bulk_mode"] == "disabled"
    assert float(np.abs(bulk_output - bulk_original).mean()) < float(np.abs(bulk_baseline - bulk_original).mean())


def test_hair_attenuation_reuses_cached_color_estimates_for_same_session(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = np.full((256, 192, 3), 32, dtype=np.uint8)
    frame[8:140, 20:172] = np.array([28, 36, 72], dtype=np.uint8)
    frame[64:220, 44:148] = np.array([170, 196, 222], dtype=np.uint8)
    landmarks = _build_landmarks()
    hair_confidence_mask = np.zeros((256, 192), dtype=np.float32)
    hair_confidence_mask[8:140, 20:172] = 0.96
    attenuator = HairAttenuator(
        segmentation_confidence_threshold=0.25,
        strength=0.92,
    )

    calls = {"skin": 0, "boundary": 0, "background": 0}

    def fake_skin(*args, **kwargs):
        calls["skin"] += 1
        return np.array([140.0, 170.0, 205.0], dtype=np.float32)

    def fake_boundary(*args, **kwargs):
        calls["boundary"] += 1
        return np.array([144.0, 174.0, 208.0], dtype=np.float32)

    def fake_background(*args, **kwargs):
        calls["background"] += 1
        return np.array([34.0, 38.0, 44.0], dtype=np.float32)

    monkeypatch.setattr(attenuator, "_estimate_skin_color", fake_skin)
    monkeypatch.setattr(attenuator, "_estimate_lower_boundary_skin_color", fake_boundary)
    monkeypatch.setattr(attenuator, "_estimate_background_color", fake_background)

    user_row = {
        "_apply_session_id": "cache-session-a",
        "face_bbox": {"x": 44, "y": 44, "w": 104, "h": 152},
        "pose": {"yaw_float": 0.0, "pitch_float": 0.0, "roll_float": 0.0},
    }

    _, first_metadata = attenuator.apply_with_metadata(
        frame,
        landmarks,
        user_row=user_row,
        hair_confidence_mask=hair_confidence_mask,
    )
    _, second_metadata = attenuator.apply_with_metadata(
        frame,
        landmarks,
        user_row=user_row,
        hair_confidence_mask=hair_confidence_mask,
    )

    assert calls == {"skin": 1, "boundary": 1, "background": 1}
    assert np.array_equal(first_metadata["scalp_color"], second_metadata["scalp_color"])
