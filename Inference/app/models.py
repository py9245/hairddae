from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PointModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    confidence: float = 1.0


class PoseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yaw_float: float
    pitch_float: float
    roll_float: float
    yaw_1deg: int
    pitch_1deg: int
    roll_1deg: int


class ImageSizeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(ge=1)
    height: int = Field(ge=1)


class FaceBoxModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int
    y: int
    w: int = Field(ge=0)
    h: int = Field(ge=0)


class FeatureMessageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["feature"]
    feature_schema_version: int
    coordinate_space: str
    anchor_set: str
    transform_version: str
    seq: int = Field(ge=1)
    ts_ms: int = Field(ge=0)
    apply_session_id: str
    hair_id: int = Field(ge=1)
    image_size: ImageSizeModel
    pose: PoseModel
    face_bbox: FaceBoxModel
    anchors: dict[str, PointModel]
