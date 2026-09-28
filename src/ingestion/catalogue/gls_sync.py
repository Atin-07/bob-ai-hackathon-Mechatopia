"""Pushes camera metadata to the GLS/Registry system.

This is a completely separate data flow from AI dispatch -- no frames,
no batching, no sampling. Just: on every catalogue refresh, tell GLS
what cameras exist, where they are, and how to reach them for live
preview (WebRTC/WHEP) or fallback (HLS). AI processing continues to use
RTSP directly and is untouched by this module.
"""

import asyncio
import logging

import httpx

from catalogue.models import Camera

logger = logging.getLogger("gls_sync")


def _camera_to_gls_payload(camera: Camera) -> dict:
    """Shape one Camera into the metadata format GLS expects."""

    return {
        "camera_id": camera.camera_id,
        "organization_id": camera.organization_id,
        "name": camera.name,
        "location": camera.location,
        "status": "online" if camera.live else "offline",
        "camera_properties": {
            "codec": camera.codec,
            "width": camera.stream_properties.width,
            "height": camera.stream_properties.height,
            "fps": camera.stream_properties.fps,
            "bitrate_kbps": camera.stream_properties.bitrate_kbps,
        },
        # GLS uses WebRTC for live browser preview when a camera is
        # clicked on the map; HLS is the restricted-network fallback.
        # RTSP is included too in case GLS needs it internally, but it
        # is never used for browser playback.
        "webrtc_url": camera.webrtc_url,
        "hls_url": camera.hls_url,
        "rtsp_url": camera.rtsp_url,
    }


class GLSSync:
    def __init__(self, gls_url: str, timeout_seconds: float = 5.0, service_key: str = ""):
        self.gls_url = gls_url.rstrip("/")
        self.service_key = service_key
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def push(self, cameras: list[Camera]) -> bool:
        payload = {"cameras": [_camera_to_gls_payload(c) for c in cameras]}
        headers = {"X-Service-Key": self.service_key} if self.service_key else {}
        try:
            response = await self._client.post(self.gls_url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info("Pushed %d cameras to GLS", len(cameras))
            return True
        except (httpx.TimeoutException, httpx.TransportError) as error:
            logger.error("Network error pushing to GLS at %s: %s", self.gls_url, error)
            return False
        except httpx.HTTPStatusError as error:
            logger.error(
                "GLS endpoint returned status %s", error.response.status_code
            )
            return False

    async def close(self) -> None:
        await self._client.aclose()