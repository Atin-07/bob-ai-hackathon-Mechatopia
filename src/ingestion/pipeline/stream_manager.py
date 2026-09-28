"""Per-camera RTSP connection lifecycle: connect, reconnect with backoff,
and hand decoded frames off to a per-camera callback (the sampler/buffer
stage owns what happens to each frame after this).
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from catalogue.models import Camera
from config.settings import Settings
from pipeline.decoder import DecodedFrame, StreamDecoder

logger = logging.getLogger("stream_manager")

# A frame's PTS jumping backward by more than this is treated as a hard
# scene discontinuity (loop point) rather than normal jitter.
_DISCONTINUITY_THRESHOLD_MS = 2000.0


class CameraStreamWorker:
    """Owns the connect/read/reconnect loop for exactly one camera."""

    def __init__(
        self,
        camera: Camera,
        settings: Settings,
        on_frame,           # async callable: (DecodedFrame) -> None
        executor: ThreadPoolExecutor,  # dedicated pool, shared across all camera workers
        on_discontinuity=None,  # callable: (camera_id: str) -> None, sync ok
    ):
        self.camera = camera
        self.settings = settings
        self.on_frame = on_frame
        self.on_discontinuity = on_discontinuity
        self._executor = executor
        self._decoder = StreamDecoder(
            camera_id=camera.camera_id,
            organization_id=camera.organization_id,
            rtsp_url=camera.rtsp_url,
        )
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_pts_ms: float | None = None

    def start(self) -> None:
        """Start the background read loop as an asyncio task."""

        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the read loop and close the connection."""

        self._running = False

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._decoder.close()

    async def _run(self) -> None:
        backoff_seconds = self.settings.reconnect_initial_backoff_seconds
        loop = asyncio.get_running_loop()

        while self._running:
            opened = await loop.run_in_executor(self._executor, self._decoder.open)

            if not opened:
                logger.warning(
                    "%s: connect failed, retrying in %.1fs",
                    self.camera.camera_id,
                    backoff_seconds,
                )
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(
                    backoff_seconds * 2,
                    self.settings.reconnect_max_backoff_seconds,
                )
                continue

            # Connected successfully -- reset backoff for next time we need it.
            backoff_seconds = self.settings.reconnect_initial_backoff_seconds
            self._last_pts_ms = None

            await self._read_until_disconnected()

            if self._running:
                logger.info(
                    "%s: stream ended/disconnected, reconnecting in %.1fs",
                    self.camera.camera_id,
                    backoff_seconds,
                )
                self._decoder.close()
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(
                    backoff_seconds * 2,
                    self.settings.reconnect_max_backoff_seconds,
                )

    async def _read_until_disconnected(self) -> None:
        """Read frames until the decoder reports a failed read."""

        loop = asyncio.get_running_loop()

        while self._running:
            frame = await loop.run_in_executor(self._executor, self._decoder.read_frame)

            if frame is None:
                # Failed read -- real disconnect, not a decode warning.
                return

            if self._is_discontinuity(frame.pts_ms):
                logger.info(
                    "%s: scene discontinuity detected (pts jumped from %.0f to %.0f), "
                    "resetting stream state",
                    self.camera.camera_id,
                    self._last_pts_ms,
                    frame.pts_ms,
                )
                self._decoder.reset_for_discontinuity()

                # The sampler upstream (owned by main.py) has its own
                # last_selected_pts_ms based on the old timeline. Without
                # this callback it will see every post-cut PTS as
                # non-monotonic (elapsed_ms <= 0) and silently reject
                # every frame forever.
                if self.on_discontinuity is not None:
                    self.on_discontinuity(self.camera.camera_id)

            self._last_pts_ms = frame.pts_ms

            await self.on_frame(frame)

    def _is_discontinuity(self, pts_ms: float) -> bool:
        if self._last_pts_ms is None:
            return False

        return (self._last_pts_ms - pts_ms) > _DISCONTINUITY_THRESHOLD_MS


class StreamManager:
    """Owns one CameraStreamWorker per active camera.

    Only opens streams for cameras currently in the live catalogue, up to
    settings.max_active_streams. Cameras that disappear from the catalogue
    (or go offline) have their worker stopped and removed.
    """

    def __init__(self, settings: Settings, on_frame, on_discontinuity=None):
        self.settings = settings
        self.on_frame = on_frame
        self.on_discontinuity = on_discontinuity
        self._workers: dict[str, CameraStreamWorker] = {}

        # Dedicated pool, sized to guarantee every possible active camera
        # always has a thread available for its blocking cap.read() call.
        # Deliberately NOT using asyncio.to_thread's shared default pool
        # (min(32, cpu_count()+4)) -- that size has nothing to do with
        # camera count and can silently queue reads once streams > pool size.
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_active_streams,
            thread_name_prefix="rtsp-reader",
        )

    async def sync_cameras(self, live_cameras: list[Camera]) -> None:
        """Reconcile active workers against the latest live camera list."""

        live_by_id = {camera.camera_id: camera for camera in live_cameras}

        # Stop workers for cameras no longer live/present.
        for camera_id in list(self._workers.keys()):
            if camera_id not in live_by_id:
                logger.info("%s: no longer live, stopping stream", camera_id)
                await self._workers[camera_id].stop()
                del self._workers[camera_id]

        # Start workers for new live cameras, respecting max_active_streams.
        for camera_id, camera in live_by_id.items():
            if camera_id in self._workers:
                continue

            if len(self._workers) >= self.settings.max_active_streams:
                logger.warning(
                    "Max active streams (%d) reached, skipping %s",
                    self.settings.max_active_streams,
                    camera_id,
                )
                continue

            worker = CameraStreamWorker(
                camera, self.settings, self.on_frame, self._executor, self.on_discontinuity
            )
            worker.start()
            self._workers[camera_id] = worker
            logger.info("%s: stream worker started", camera_id)

    async def stop_all(self) -> None:
        """Stop every active camera worker (graceful shutdown)."""

        for camera_id, worker in list(self._workers.items()):
            await worker.stop()
        self._workers.clear()
        self._executor.shutdown(wait=True)

    def active_camera_ids(self) -> list[str]:
        return list(self._workers.keys())