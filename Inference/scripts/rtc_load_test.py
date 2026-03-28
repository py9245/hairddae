from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import uuid
from urllib import request

import cv2
import jwt
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


@dataclass
class ClientStats:
    session_id: str
    frames_sent: int = 0
    messages_received: int = 0
    remote_frames_received: int = 0


class StaticImageTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, frame_bgr, fps: float) -> None:
        super().__init__()
        self._frame_bgr = frame_bgr
        self._fps = max(1.0, float(fps))
        self._frame_period = 1.0 / self._fps
        self._next_ts = 0.0
        self.frames_sent = 0

    async def recv(self) -> VideoFrame:
        pts, time_base = await self.next_timestamp()
        frame = VideoFrame.from_ndarray(self._frame_bgr, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        self.frames_sent += 1
        return frame


def _build_connect_ticket(
    *,
    session_id: str,
    hair_id: int,
    dataset_code: str,
) -> str:
    now = datetime.now(timezone.utc)
    secret = _env_str("APP_SECURITY_JWT_SECRET", "")
    issuer = _env_str("INFERENCE_JWT_ISSUER", "hairddae")
    audience = _env_str("INFERENCE_TICKET_AUDIENCE", "inference")
    node_id = _env_str("INFERENCE_NODE_ID", "infer-gpu-01")
    schema_version = _env_int("INFERENCE_FEATURE_SCHEMA_VERSION", 2)
    if not secret:
        raise RuntimeError("APP_SECURITY_JWT_SECRET is missing")
    payload = {
        "sub": "rtc-load-test-user",
        "jti": f"rtc-load-{uuid.uuid4()}",
        "iss": issuer,
        "aud": audience,
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "tokenType": "INFERENCE_CONNECT",
        "single_use": True,
        "node": node_id,
        "sid": session_id,
        "did": f"device-{session_id}",
        "hid": int(hair_id),
        "ver": int(schema_version),
        "dataset_code": str(dataset_code),
        "representative_asset_id": None,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _post_offer(offer_sdp: str, offer_type: str, connect_ticket: str, endpoint: str) -> dict[str, str]:
    payload = json.dumps(
        {
            "sdp": offer_sdp,
            "type": offer_type,
            "connect_ticket": connect_ticket,
        }
    ).encode("utf-8")
    req = request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


async def _drain_remote_track(track, stats: ClientStats) -> None:
    try:
        while True:
            await track.recv()
            stats.remote_frames_received += 1
    except Exception:
        return


async def run_client(
    *,
    client_index: int,
    duration_sec: int,
    endpoint: str,
    frame_bgr,
    fps: float,
    hair_id: int,
    dataset_code: str,
) -> ClientStats:
    session_id = f"rtc-load-{client_index}-{uuid.uuid4().hex[:8]}"
    stats = ClientStats(session_id=session_id)
    connect_ticket = _build_connect_ticket(
        session_id=session_id,
        hair_id=hair_id,
        dataset_code=dataset_code,
    )
    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=[]))
    image_height, image_width = frame_bgr.shape[:2]
    track = StaticImageTrack(frame_bgr, fps)
    pc.addTrack(track)
    control_channel = pc.createDataChannel("control")
    channel_opened = asyncio.Event()
    remote_tasks: list[asyncio.Task] = []

    @control_channel.on("open")
    def _on_open() -> None:
        hello_payload = {
            "type": "hello",
            "session_version": 1,
            "stage_width": int(image_width),
            "stage_height": int(image_height),
            "fps": float(fps),
            "mirrored": False,
        }
        control_channel.send(json.dumps(hello_payload))
        channel_opened.set()

    @pc.on("track")
    def _on_track(remote_track) -> None:
        remote_tasks.append(asyncio.create_task(_drain_remote_track(remote_track, stats)))

    @control_channel.on("message")
    def _on_message(message) -> None:
        _ = message
        stats.messages_received += 1

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    answer_payload = await asyncio.to_thread(
        _post_offer,
        pc.localDescription.sdp,
        pc.localDescription.type,
        connect_ticket,
        endpoint,
    )
    await pc.setRemoteDescription(
        RTCSessionDescription(sdp=answer_payload["sdp"], type=answer_payload["type"])
    )

    try:
        await asyncio.wait_for(channel_opened.wait(), timeout=10)
        await asyncio.sleep(max(1, int(duration_sec)))
    finally:
        stats.frames_sent = track.frames_sent
        for task in remote_tasks:
            task.cancel()
        await pc.close()
    return stats


async def main_async(args: argparse.Namespace) -> int:
    frame_bgr = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if frame_bgr is None:
        raise FileNotFoundError(f"failed to read image: {args.image}")
    tasks = [
        run_client(
            client_index=index,
            duration_sec=args.duration,
            endpoint=args.endpoint,
            frame_bgr=frame_bgr,
            fps=args.fps,
            hair_id=args.hair_id,
            dataset_code=args.dataset_code,
        )
        for index in range(1, args.clients + 1)
    ]
    results = await asyncio.gather(*tasks)
    for result in results:
        print(
            json.dumps(
                {
                    "session_id": result.session_id,
                    "frames_sent": result.frames_sent,
                    "messages_received": result.messages_received,
                    "remote_frames_received": result.remote_frames_received,
                },
                ensure_ascii=False,
            )
        )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clients", type=int, default=2)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--hair-id", type=int, default=3)
    parser.add_argument("--dataset-code", default="0003")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8090/rtc/offer")
    parser.add_argument(
        "--image",
        type=Path,
        default=Path("/home/ubuntu/S14P21M101/static/0003/댄디컷_댄디컷.png"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
