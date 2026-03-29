from __future__ import annotations

from types import SimpleNamespace

from app import rtc_codec_accel


class _FakeCodec:
    def __init__(self, mime_type: str) -> None:
        self.mimeType = mime_type


def test_nvenc_codec_options_omit_zerolatency() -> None:
    options = rtc_codec_accel._nvenc_codec_options()
    assert options["preset"] == "p4"
    assert options["rc"] == "cbr"
    assert "zerolatency" not in options


def test_make_get_encoder_uses_nvenc_for_h264(monkeypatch):
    monkeypatch.setattr(
        rtc_codec_accel,
        "NvencH264Encoder",
        lambda: "nvenc-encoder",
    )

    original_calls: list[str] = []

    def _original(codec):
        original_calls.append(codec.mimeType)
        return "original-encoder"

    patched = rtc_codec_accel._make_get_encoder(
        _original,
        enable_nvenc=True,
        nvenc_available=True,
    )

    assert patched(_FakeCodec("video/H264")) == "nvenc-encoder"
    assert patched(_FakeCodec("video/VP8")) == "original-encoder"
    assert original_calls == ["video/VP8"]


def test_make_get_decoder_uses_cuvid_for_h264(monkeypatch):
    monkeypatch.setattr(
        rtc_codec_accel,
        "CuvidH264Decoder",
        lambda: "cuvid-decoder",
    )

    original_calls: list[str] = []

    def _original(codec):
        original_calls.append(codec.mimeType)
        return "original-decoder"

    patched = rtc_codec_accel._make_get_decoder(
        _original,
        enable_cuvid=True,
        cuvid_available=True,
    )

    assert patched(_FakeCodec("video/H264")) == "cuvid-decoder"
    assert patched(_FakeCodec("audio/opus")) == "original-decoder"
    assert original_calls == ["audio/opus"]


def test_apply_rtc_codec_acceleration_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(rtc_codec_accel, "_PATCH_APPLIED", False)

    class _CodecsModule:
        get_encoder = staticmethod(lambda codec: "orig-encoder")
        get_decoder = staticmethod(lambda codec: "orig-decoder")

    class _SenderModule:
        get_encoder = staticmethod(lambda codec: "sender-encoder")

    class _ReceiverModule:
        get_decoder = staticmethod(lambda codec: "receiver-decoder")

    monkeypatch.setitem(__import__("sys").modules, "aiortc.codecs", _CodecsModule)
    monkeypatch.setitem(__import__("sys").modules, "aiortc.rtcrtpsender", _SenderModule)
    monkeypatch.setitem(__import__("sys").modules, "aiortc.rtcrtpreceiver", _ReceiverModule)

    rtc_codec_accel.apply_rtc_codec_acceleration(
        SimpleNamespace(
            rtc_enable_h264_nvenc=False,
            rtc_enable_h264_cuvid=False,
        )
    )

    assert rtc_codec_accel._PATCH_APPLIED is False
