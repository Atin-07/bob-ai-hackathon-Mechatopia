"""HTTP client for the government (or mock) camera catalogue endpoint.

This always goes over real HTTP -- it never reads local files directly --
so that swapping the mock catalogue for a real government endpoint later
requires only a config change (base_url), not a code change.
"""

import asyncio
import logging
from typing import Awaitable, Callable

import httpx

from .models import Camera

logger = logging.getLogger("catalog_client")

_KNOWN_CAMERA_FIELDS = {
    "camera_id",
    "organization_id",
    "name",
    "location",
    "codec",
    "live",
    "stream_properties",
    "rtsp_url",
    "webrtc_url",
    "hls_url",
}


class CatalogClient:
    """Polls GET {base_url}/api/ingest and yields validated Camera objects."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 5.0,
        refresh_interval_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.refresh_interval_seconds = refresh_interval_seconds
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def fetch_catalogue(self) -> list[Camera]:
        """Fetch and parse the full camera catalogue.

        Returns an empty list (and logs) on any network error, timeout, or
        non-200 response -- callers should keep running on their
        last-known-good catalogue rather than crash.
        """

        url = f"{self.base_url}/api/ingest"

        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.TransportError) as error:
            logger.error("Network error fetching catalogue from %s: %s", url, error)
            return []
        except httpx.HTTPStatusError as error:
            logger.error(
                "Catalogue endpoint returned status %s for %s",
                error.response.status_code,
                url,
            )
            return []

        try:
            payload = response.json()
            raw_cameras = payload.get("cameras", [])
        except ValueError as error:
            logger.error("Catalogue response was not valid JSON: %s", error)
            return []

        cameras: list[Camera] = []

        for raw_camera in raw_cameras:
            try:
                filtered = {
                    key: value
                    for key, value in raw_camera.items()
                    if key in _KNOWN_CAMERA_FIELDS
                }
                cameras.append(Camera(**filtered))
            except Exception as error:
                logger.warning(
                    "Skipping invalid camera entry '%s': %s",
                    raw_camera.get("camera_id", "<unknown>"),
                    error,
                )
                continue

        return cameras

    async def get_live_cameras(self) -> list[Camera]:
        """Fetch the catalogue and return only cameras marked live."""

        cameras = await self.fetch_catalogue()
        return [camera for camera in cameras if camera.live]

    async def start_periodic_refresh(
        self,
        callback: Callable[[list[Camera]], Awaitable[None]],
    ) -> None:
        """Continuously poll the catalogue and invoke callback with updates.

        Runs until the enclosing asyncio task is cancelled. CancelledError
        is logged and re-raised so callers can await this as a managed task.
        """

        try:
            while True:
                cameras = await self.get_live_cameras()
                await callback(cameras)
                await asyncio.sleep(self.refresh_interval_seconds)
        except asyncio.CancelledError:
            logger.info("Catalogue refresh loop stopped")
            raise

    async def close(self) -> None:
        """Close the underlying HTTP client."""

        await self._client.aclose()

    async def __aenter__(self) -> "CatalogClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()