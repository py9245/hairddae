from __future__ import annotations

import fractions
import logging
from typing import Any, Callable

import av

logger = logging.getLogger("uvicorn.error")

_PATCH_APPLIED = False


def _codec_available(name: str, mode: str) -> bool:
    try:
        av.CodecContext.create(name, mode)
        return True
    except Exception:
        logger.warning("rtc codec acceleration unavailable: codec=%s mode=%s", name, mode)
        return False


class NvencH264Encoder:
    def __init__(self) -> None:
        from aiortc.codecs.h264 import H264Encoder

        self._fallback = H264Encoder()
        self._using_fallback = False
        self._buffer_data = b""
        self._buffer_pts: int | None = None
        self._codec = None
        self._target_bitrate = self._fallback.target_bitrate
        self._h264_module = __import__("aiortc.codecs.h264", fromlist=["dummy"])

    def _switch_to_fallback(self) -> None:
        if self._using_fallback:
            return
        self._using_fallback = True
        self._fallback.target_bitrate = self._target_bitrate
        self._codec = None
        logger.warning("rtc codec acceleration falling back to libx264 encoder")

    def _reset_codec_if_needed(self, frame: av.VideoFrame) -> None:
        codec = self._codec
        if codec is None:
            return
        if (
            frame.width != codec.width
            or frame.height != codec.height
            or abs(self.target_bitrate - codec.bit_rate) / max(codec.bit_rate, 1) > 0.1
        ):
            self._buffer_data = b""
            self._buffer_pts = None
            self._codec = None

    def _create_codec(self, frame: av.VideoFrame) -> Any:
        codec = av.CodecContext.create("h264_nvenc", "w")
        codec.width = frame.width
        codec.height = frame.height
        codec.bit_rate = self.target_bitrate
        codec.pix_fmt = "yuv420p"
        codec.framerate = fractions.Fraction(self._h264_module.MAX_FRAME_RATE, 1)
        codec.time_base = fractions.Fraction(1, self._h264_module.MAX_FRAME_RATE)
        codec.options = {
            "preset": "p4",
            "rc": "cbr",
            "zerolatency": "1",
        }
        try:
            codec.profile = "Baseline"
        except Exception:
            logger.debug("rtc codec acceleration could not set nvenc profile=Baseline")
        return codec

    def _encode_frame(self, frame: av.VideoFrame, force_keyframe: bool):
        if self._using_fallback:
            yield from self._fallback._encode_frame(frame, force_keyframe)
            return

        self._reset_codec_if_needed(frame)

        if force_keyframe:
            frame.pict_type = av.video.frame.PictureType.I
        else:
            frame.pict_type = av.video.frame.PictureType.NONE

        if self._codec is None:
            try:
                self._codec = self._create_codec(frame)
            except Exception:
                logger.exception("rtc codec acceleration failed to initialize h264_nvenc encoder")
                self._switch_to_fallback()
                yield from self._fallback._encode_frame(frame, force_keyframe)
                return

        data_to_send = b""
        try:
            for package in self._codec.encode(frame):
                data_to_send += bytes(package)
        except av.FFmpegError:
            logger.exception("rtc codec acceleration failed during h264_nvenc encode")
            self._switch_to_fallback()
            yield from self._fallback._encode_frame(frame, force_keyframe)
            return

        if data_to_send:
            yield from self._h264_module.H264Encoder._split_bitstream(data_to_send)

    def encode(
        self,
        frame: av.frame.Frame,
        force_keyframe: bool = False,
    ) -> tuple[list[bytes], int]:
        assert isinstance(frame, av.VideoFrame)
        packages = self._encode_frame(frame, force_keyframe)
        timestamp = self._h264_module.convert_timebase(
            frame.pts,
            frame.time_base,
            self._h264_module.VIDEO_TIME_BASE,
        )
        return self._h264_module.H264Encoder._packetize(packages), timestamp

    def pack(self, packet: av.packet.Packet) -> tuple[list[bytes], int]:
        if self._using_fallback:
            return self._fallback.pack(packet)
        packages = self._h264_module.H264Encoder._split_bitstream(bytes(packet))
        timestamp = self._h264_module.convert_timebase(
            packet.pts,
            packet.time_base,
            self._h264_module.VIDEO_TIME_BASE,
        )
        return self._h264_module.H264Encoder._packetize(packages), timestamp

    @property
    def target_bitrate(self) -> int:
        return self._target_bitrate

    @target_bitrate.setter
    def target_bitrate(self, bitrate: int) -> None:
        h264_module = self._h264_module
        bitrate = max(h264_module.MIN_BITRATE, min(bitrate, h264_module.MAX_BITRATE))
        self._target_bitrate = bitrate
        self._fallback.target_bitrate = bitrate
        if self._codec is not None:
            try:
                self._codec.bit_rate = bitrate
            except Exception:
                self._codec = None


class CuvidH264Decoder:
    def __init__(self) -> None:
        from aiortc.codecs.h264 import H264Decoder

        self._fallback = None
        try:
            self.codec = av.CodecContext.create("h264_cuvid", "r")
            self._using_fallback = False
        except Exception:
            logger.exception("rtc codec acceleration failed to initialize h264_cuvid decoder")
            self._fallback = H264Decoder()
            self._using_fallback = True

    def decode(self, encoded_frame: Any) -> list[Any]:
        if self._using_fallback:
            return self._fallback.decode(encoded_frame)
        try:
            packet = av.Packet(encoded_frame.data)
            packet.pts = encoded_frame.timestamp
            from aiortc.mediastreams import VIDEO_TIME_BASE

            packet.time_base = VIDEO_TIME_BASE
            return self.codec.decode(packet)
        except av.FFmpegError:
            logger.exception("rtc codec acceleration failed during h264_cuvid decode")
            if self._fallback is None:
                from aiortc.codecs.h264 import H264Decoder

                self._fallback = H264Decoder()
            self._using_fallback = True
            return self._fallback.decode(encoded_frame)


def _make_get_encoder(
    original_get_encoder: Callable[[Any], Any],
    *,
    enable_nvenc: bool,
    nvenc_available: bool,
) -> Callable[[Any], Any]:
    def _get_encoder(codec: Any) -> Any:
        mime_type = str(getattr(codec, "mimeType", "")).lower()
        if enable_nvenc and nvenc_available and mime_type == "video/h264":
            return NvencH264Encoder()
        return original_get_encoder(codec)

    return _get_encoder


def _make_get_decoder(
    original_get_decoder: Callable[[Any], Any],
    *,
    enable_cuvid: bool,
    cuvid_available: bool,
) -> Callable[[Any], Any]:
    def _get_decoder(codec: Any) -> Any:
        mime_type = str(getattr(codec, "mimeType", "")).lower()
        if enable_cuvid and cuvid_available and mime_type == "video/h264":
            return CuvidH264Decoder()
        return original_get_decoder(codec)

    return _get_decoder


def apply_rtc_codec_acceleration(settings: Any) -> None:
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return

    enable_nvenc = bool(getattr(settings, "rtc_enable_h264_nvenc", False))
    enable_cuvid = bool(getattr(settings, "rtc_enable_h264_cuvid", False))
    if not enable_nvenc and not enable_cuvid:
        logger.info("rtc codec acceleration disabled")
        return

    try:
        import aiortc.codecs as codecs_module
        import aiortc.rtcrtpsender as sender_module
        import aiortc.rtcrtpreceiver as receiver_module
    except ImportError:
        logger.warning("rtc codec acceleration unavailable: aiortc import failed")
        return

    nvenc_available = enable_nvenc and _codec_available("h264_nvenc", "w")
    cuvid_available = enable_cuvid and _codec_available("h264_cuvid", "r")

    patched_get_encoder = _make_get_encoder(
        codecs_module.get_encoder,
        enable_nvenc=enable_nvenc,
        nvenc_available=nvenc_available,
    )
    patched_get_decoder = _make_get_decoder(
        codecs_module.get_decoder,
        enable_cuvid=enable_cuvid,
        cuvid_available=cuvid_available,
    )

    codecs_module.get_encoder = patched_get_encoder
    codecs_module.get_decoder = patched_get_decoder
    sender_module.get_encoder = patched_get_encoder
    receiver_module.get_decoder = patched_get_decoder
    _PATCH_APPLIED = True

    logger.info(
        "rtc codec acceleration active: nvenc_enabled=%s nvenc_available=%s cuvid_enabled=%s cuvid_available=%s",
        enable_nvenc,
        nvenc_available,
        enable_cuvid,
        cuvid_available,
    )
