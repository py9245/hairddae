from __future__ import annotations

import fractions
import logging
import os
import time
from functools import lru_cache
from threading import Lock
from typing import cast

import av
from av.frame import Frame
from aiortc.codecs import h264 as h264_module
from aiortc.jitterbuffer import JitterFrame
from aiortc.mediastreams import VIDEO_TIME_BASE

from app.acceleration import detect_runtime_acceleration
from app.config import Settings


logger = logging.getLogger("uvicorn.error")

_PATCH_INSTALLED = False
_NVENC_PROBE_WIDTH = 432
_NVENC_PROBE_HEIGHT = 240
_TIMING_LOG_ENABLED = False
_TIMING_LOG_INTERVAL_MS = 1000


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


class _CodecTimingWindow:
    def __init__(self) -> None:
        self.count = 0
        self.total_ms = 0.0
        self.max_ms = 0.0
        self.total_payload_bytes = 0
        self.total_output_frames = 0
        self.codec_names: set[str] = set()


_codec_timing_lock = Lock()
_codec_timing_windows = {
    "encode": _CodecTimingWindow(),
    "decode": _CodecTimingWindow(),
}
_codec_timing_last_log_at_ms = {
    "encode": 0.0,
    "decode": 0.0,
}


def _configure_timing_logging(settings: Settings | None = None) -> None:
    global _TIMING_LOG_ENABLED, _TIMING_LOG_INTERVAL_MS
    if settings is not None:
        _TIMING_LOG_ENABLED = settings.rtc_h264_timing_log_enabled
        _TIMING_LOG_INTERVAL_MS = settings.rtc_h264_timing_log_interval_ms
        return
    _TIMING_LOG_ENABLED = _env_bool("INFERENCE_RTC_H264_TIMING_LOG_ENABLED", False)
    _TIMING_LOG_INTERVAL_MS = _env_int("INFERENCE_RTC_H264_TIMING_LOG_INTERVAL_MS", 1000)


def _record_codec_timing(
    kind: str,
    *,
    codec_name: str,
    elapsed_ms: float,
    payload_bytes: int = 0,
    output_frames: int = 0,
) -> None:
    if not _TIMING_LOG_ENABLED:
        return

    now_ms = time.monotonic() * 1000.0
    with _codec_timing_lock:
        window = _codec_timing_windows[kind]
        window.count += 1
        window.total_ms += elapsed_ms
        window.max_ms = max(window.max_ms, elapsed_ms)
        window.total_payload_bytes += payload_bytes
        window.total_output_frames += output_frames
        window.codec_names.add(codec_name)

        interval_ms = max(float(_TIMING_LOG_INTERVAL_MS), 1.0)
        elapsed_window_ms = now_ms - _codec_timing_last_log_at_ms[kind]
        if elapsed_window_ms < interval_ms:
            return

        _codec_timing_last_log_at_ms[kind] = now_ms
        count = max(window.count, 1)
        window_seconds = max(elapsed_window_ms / 1000.0, 1e-3)
        logger.info(
            (
                "rtc h264 %s timing: samples=%s rate=%.2f avg_ms=%.2f max_ms=%.2f "
                "avg_payload_kb=%.2f avg_output_frames=%.2f codecs=%s"
            ),
            kind,
            window.count,
            window.count / window_seconds,
            window.total_ms / count,
            window.max_ms,
            (window.total_payload_bytes / count) / 1024.0,
            window.total_output_frames / count,
            sorted(window.codec_names),
        )
        _codec_timing_windows[kind] = _CodecTimingWindow()


def _pyav_codec_available(codec_name: str) -> bool:
    try:
        return codec_name in av.codecs_available
    except Exception:
        return False


@lru_cache(maxsize=1)
def _probe_h264_nvenc() -> bool:
    runtime = detect_runtime_acceleration()
    if not runtime.nvidia_runtime_visible or not _pyav_codec_available("h264_nvenc"):
        return False

    try:
        codec = av.CodecContext.create("h264_nvenc", "w")
        codec.width = _NVENC_PROBE_WIDTH
        codec.height = _NVENC_PROBE_HEIGHT
        codec.bit_rate = 500_000
        codec.pix_fmt = "yuv420p"
        codec.framerate = fractions.Fraction(h264_module.MAX_FRAME_RATE, 1)
        codec.time_base = fractions.Fraction(1, h264_module.MAX_FRAME_RATE)
        # NVENC rejects very small probe frames, so keep the probe near real RTC sizes.
        frame = av.VideoFrame(_NVENC_PROBE_WIDTH, _NVENC_PROBE_HEIGHT, "yuv420p")
        frame.pts = 0
        frame.time_base = codec.time_base
        list(codec.encode(frame))
        return True
    except Exception as exc:
        logger.info("rtc H264 NVENC probe failed, using CPU encoder: %s", exc)
        return False


@lru_cache(maxsize=1)
def _preferred_h264_encoder_name() -> str:
    return "h264_nvenc" if _probe_h264_nvenc() else "libx264"


@lru_cache(maxsize=1)
def _preferred_h264_decoder_name() -> str:
    runtime = detect_runtime_acceleration()
    if not runtime.nvidia_runtime_visible or not _pyav_codec_available("h264_cuvid"):
        return "h264"

    try:
        av.CodecContext.create("h264_cuvid", "r")
        return "h264_cuvid"
    except Exception as exc:
        logger.info("rtc H264 CUVID probe failed, using CPU decoder: %s", exc)
        return "h264"


def get_rtc_h264_acceleration_state() -> dict[str, object]:
    return {
        "patched": _PATCH_INSTALLED,
        "preferred_encoder": _preferred_h264_encoder_name(),
        "preferred_decoder": _preferred_h264_decoder_name(),
        "nvenc_candidate_available": _pyav_codec_available("h264_nvenc"),
        "cuvid_candidate_available": _pyav_codec_available("h264_cuvid"),
        "nvenc_probe_ok": _probe_h264_nvenc(),
        "timing_logging_enabled": _TIMING_LOG_ENABLED,
        "timing_log_interval_ms": _TIMING_LOG_INTERVAL_MS,
    }


class GPUAwareH264Decoder(h264_module.H264Decoder):
    def __init__(self) -> None:
        self._fallback_codec_name = "h264"
        self._active_codec_name = _preferred_h264_decoder_name()
        self.codec = av.CodecContext.create(self._active_codec_name, "r")

    def _fallback_to_cpu(self, packet: av.Packet) -> list[Frame]:
        if self._active_codec_name == self._fallback_codec_name:
            return []

        logger.warning(
            "rtc H264 decoder fallback: %s -> %s",
            self._active_codec_name,
            self._fallback_codec_name,
        )
        self._active_codec_name = self._fallback_codec_name
        self.codec = av.CodecContext.create(self._active_codec_name, "r")
        try:
            return cast(list[Frame], self.codec.decode(packet))
        except av.FFmpegError as exc:
            logger.warning("rtc H264 decoder CPU fallback failed, dropping packet: %s", exc)
            return []

    def decode(self, encoded_frame: JitterFrame) -> list[Frame]:
        packet = av.Packet(encoded_frame.data)
        packet.pts = encoded_frame.timestamp
        packet.time_base = VIDEO_TIME_BASE
        started_at = time.perf_counter()
        decoded_frames: list[Frame] = []
        try:
            decoded_frames = cast(list[Frame], self.codec.decode(packet))
            return decoded_frames
        except av.FFmpegError as exc:
            logger.warning(
                "rtc H264 decoder %s failed, retrying on CPU: %s",
                self._active_codec_name,
                exc,
            )
            decoded_frames = self._fallback_to_cpu(packet)
            return decoded_frames
        finally:
            _record_codec_timing(
                "decode",
                codec_name=self._active_codec_name,
                elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
                payload_bytes=len(encoded_frame.data),
                output_frames=len(decoded_frames),
            )


class GPUAwareH264Encoder(h264_module.H264Encoder):
    def __init__(self) -> None:
        super().__init__()
        self._fallback_codec_name = "libx264"
        self._active_codec_name = _preferred_h264_encoder_name()

    def _reset_codec(self) -> None:
        self.buffer_data = b""
        self.buffer_pts = None
        self.codec = None

    def _create_codec(self, codec_name: str, frame: av.VideoFrame):
        codec = av.CodecContext.create(codec_name, "w")
        codec.width = frame.width
        codec.height = frame.height
        codec.bit_rate = self.target_bitrate
        codec.pix_fmt = "yuv420p"
        codec.framerate = fractions.Fraction(h264_module.MAX_FRAME_RATE, 1)
        codec.time_base = fractions.Fraction(1, h264_module.MAX_FRAME_RATE)
        if codec_name == "libx264":
            codec.options = {
                "level": "31",
                "tune": "zerolatency",
            }
            codec.profile = "Baseline"
        return codec

    def _ensure_codec(self, frame: av.VideoFrame) -> None:
        if self.codec and (
            frame.width != self.codec.width
            or frame.height != self.codec.height
            or abs(self.target_bitrate - self.codec.bit_rate) / self.codec.bit_rate > 0.1
        ):
            self._reset_codec()

        if self.codec is None:
            self.codec = self._create_codec(self._active_codec_name, frame)

    def _fallback_to_cpu(self, frame: av.VideoFrame) -> None:
        if self._active_codec_name == self._fallback_codec_name:
            raise RuntimeError("rtc H264 CPU fallback failed")

        logger.warning(
            "rtc H264 encoder fallback: %s -> %s",
            self._active_codec_name,
            self._fallback_codec_name,
        )
        self._active_codec_name = self._fallback_codec_name
        self._reset_codec()
        self.codec = self._create_codec(self._active_codec_name, frame)

    def _encode_frame(self, frame: av.VideoFrame, force_keyframe: bool):
        self._ensure_codec(frame)

        if force_keyframe:
            frame.pict_type = av.video.frame.PictureType.I
        else:
            frame.pict_type = av.video.frame.PictureType.NONE

        try:
            data_to_send = b""
            for package in self.codec.encode(frame):
                data_to_send += bytes(package)
        except av.FFmpegError as exc:
            logger.warning(
                "rtc H264 encoder %s failed, retrying on CPU: %s",
                self._active_codec_name,
                exc,
            )
            if self._active_codec_name == self._fallback_codec_name:
                raise
            self._fallback_to_cpu(frame)
            data_to_send = b""
            for package in self.codec.encode(frame):
                data_to_send += bytes(package)

        if data_to_send:
            yield from self._split_bitstream(data_to_send)

    def encode(
        self, frame: Frame, force_keyframe: bool = False
    ) -> tuple[list[bytes], int]:
        started_at = time.perf_counter()
        payloads, timestamp = super().encode(frame, force_keyframe)
        _record_codec_timing(
            "encode",
            codec_name=self._active_codec_name,
            elapsed_ms=(time.perf_counter() - started_at) * 1000.0,
            payload_bytes=sum(len(payload) for payload in payloads),
            output_frames=1,
        )
        return payloads, timestamp


def install_aiortc_h264_acceleration(settings: Settings | None = None) -> dict[str, object]:
    global _PATCH_INSTALLED
    _configure_timing_logging(settings)
    if not _PATCH_INSTALLED:
        import aiortc.codecs as codecs_module

        codecs_module.H264Decoder = GPUAwareH264Decoder
        codecs_module.H264Encoder = GPUAwareH264Encoder
        h264_module.H264Decoder = GPUAwareH264Decoder
        h264_module.H264Encoder = GPUAwareH264Encoder
        _PATCH_INSTALLED = True

    return get_rtc_h264_acceleration_state()
