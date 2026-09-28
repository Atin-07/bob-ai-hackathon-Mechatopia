"""Wires the full ingestion pipeline together:

CatalogClient (poll /api/ingest)
    -> StreamManager (one RTSP worker per live camera)
    -> FrameSampler (per camera, PTS-driven ~5fps)
    -> BufferManager (per-camera bounded queues)
    -> Batcher (batches of 4, mixed cameras)
    -> encode_batch (raw -> JPEG, only here)
    -> PayloadBuilder (JSON shape for Vehicle/Face AI)
    -> AIDispatcher (bounded queues, sends to both consumers)
"""

import asyncio
import logging
import signal
import sys
import uvicorn
from app import app
from dotenv import load_dotenv

# Must run before config.settings is imported anywhere, or env values
# loaded here won't take effect (Settings reads os.environ at import time).
load_dotenv()
from catalogue.catalog_client import CatalogClient
from catalogue.gls_sync import GLSSync
from catalogue.models import Camera
from config.settings import get_settings
from pipeline.batcher import Batcher
from pipeline.buffer_manager import BufferManager
from pipeline.decoder import DecodedFrame
from pipeline.dispatcher import AIDispatcher
from pipeline.frame_encoder import encode_batch
from pipeline.payload_builder import PayloadBuilder
from pipeline.sampler import FrameSampler
from pipeline.stream_manager import StreamManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pipeline_main")


class Pipeline:
    def __init__(self):
        self.settings = get_settings()
        self.buffer_manager = BufferManager(
            max_size_per_camera=self.settings.camera_buffer_max_size
        )
        self.samplers: dict[str, FrameSampler] = {}

        self.catalog_client = CatalogClient(
            base_url=self.settings.catalogue_base_url,
            timeout_seconds=self.settings.catalogue_timeout_seconds,
            refresh_interval_seconds=self.settings.catalogue_refresh_interval_seconds,
        )

        self.stream_manager = StreamManager(
            settings=self.settings,
            on_frame=self._on_frame,
            on_discontinuity=self._on_discontinuity,
        )

        self.batcher = Batcher(
            buffer_manager=self.buffer_manager,
            batch_size=self.settings.batch_size,
            max_wait_seconds=self.settings.batch_max_wait_seconds,
        )

        self.payload_builder = PayloadBuilder()

        self.dispatcher = AIDispatcher(
            vehicle_url=self.settings.vehicle_ai_url,
            face_url=self.settings.face_ai_url,
            queue_size=self.settings.dispatch_queue_max_size,
        )

        self.gls_sync = GLSSync(
            gls_url=self.settings.gls_registry_url,
            timeout_seconds=self.settings.catalogue_timeout_seconds,
            service_key=self.settings.service_key,
        )

        self._tasks: list[asyncio.Task] = []
        self._running = False

    def _get_sampler(self, camera_id: str) -> FrameSampler:
        sampler = self.samplers.get(camera_id)
        if sampler is None:
            sampler = FrameSampler(target_fps=self.settings.target_sample_fps)
            self.samplers[camera_id] = sampler
        return sampler

    async def _on_frame(self, frame: DecodedFrame) -> None:
        sampler = self._get_sampler(frame.camera_id)
        if sampler.should_select(frame):
            self.buffer_manager.push(frame)

    def _on_discontinuity(self, camera_id: str) -> None:
        sampler = self.samplers.get(camera_id)
        if sampler is not None:
            sampler.reset()

    async def _on_catalogue_update(self, live_cameras: list[Camera]) -> None:
        await self.stream_manager.sync_cameras(live_cameras)
        active_ids = set(self.stream_manager.active_camera_ids())
        for camera_id in self.buffer_manager.active_camera_ids():
            if camera_id not in active_ids:
                self.buffer_manager.remove_camera(camera_id)
                self.samplers.pop(camera_id, None)

    async def _dispatch_batches(self) -> None:
        async def on_batch(batch: list[DecodedFrame]) -> None:
            encoded = encode_batch(batch)
            if not encoded:
                return
            payload = self.payload_builder.build(encoded)
            vehicle_ok = await self.dispatcher.submit_vehicle(payload)
            face_ok = await self.dispatcher.submit_face(payload)
            if not vehicle_ok:
                logger.warning("Vehicle AI queue full, batch dropped for vehicle side")
            if not face_ok:
                logger.warning("Face AI queue full, batch dropped for face side")

        await self.batcher.run(on_batch)

    async def _push_gls_loop(self) -> None:
        try:
            while True:
                cameras = await self.catalog_client.fetch_catalogue()
                await self.gls_sync.push(cameras)
                await asyncio.sleep(self.settings.gls_push_interval_seconds)
        except asyncio.CancelledError:
            logger.info("GLS push loop stopped")
            raise

    async def start(self) -> None:
        self._running = True
        await self.dispatcher.start()
        self._tasks = [
            asyncio.create_task(
                self.catalog_client.start_periodic_refresh(self._on_catalogue_update)
            ),
            asyncio.create_task(self._dispatch_batches()),
            asyncio.create_task(self._push_gls_loop()),
        ]
        logger.info("Pipeline started")

    async def stop(self) -> None:
        logger.info("Pipeline shutting down...")
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.stream_manager.stop_all()
        await self.dispatcher.stop()
        await self.gls_sync.close()
        await self.catalog_client.close()
        logger.info("Pipeline stopped cleanly")


async def main() -> None:
    settings = get_settings()
    pipeline = Pipeline()
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
    else:
        # Windows fallback: rely on KeyboardInterrupt
        async def wait_for_stop():
            try:
                await stop_event.wait()
            except asyncio.CancelledError:
                pass
        asyncio.create_task(wait_for_stop())

    config = uvicorn.Config(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    await pipeline.start()

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        stop_event.set()

    await pipeline.stop()
    server.should_exit = True
    await server_task


if __name__ == "__main__":
    asyncio.run(main())
