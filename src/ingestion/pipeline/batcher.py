"""Groups sampled frames from any mix of cameras into fixed-size batches
for dispatch to Vehicle AI and Face AI. A batch does not need to come from
a single camera -- it's whichever frames are next available across all
per-camera buffers.
"""

import asyncio
import logging

from pipeline.buffer_manager import BufferManager
from pipeline.decoder import DecodedFrame

logger = logging.getLogger("batcher")


class Batcher:
    """Pulls frames from a BufferManager and assembles them into batches.

    A batch is emitted when either:
      - batch_size frames have been collected, or
      - max_wait_seconds has elapsed since the first frame in the batch
        was collected (so batches don't stall indefinitely waiting for a
        4th frame during low camera activity).
    """

    def __init__(
        self,
        buffer_manager: BufferManager,
        batch_size: int = 4,
        max_wait_seconds: float = 1.0,
        poll_interval_seconds: float = 0.01,
    ):
        self.buffer_manager = buffer_manager
        self.batch_size = batch_size
        self.max_wait_seconds = max_wait_seconds
        self.poll_interval_seconds = poll_interval_seconds

    async def next_batch(self) -> list[DecodedFrame]:
        """Block (async) until a batch is ready, then return it.

        Returns fewer than batch_size frames only if max_wait_seconds
        elapses with at least one frame collected. Never returns an empty
        list -- it keeps polling until at least one frame is available.
        """

        batch: list[DecodedFrame] = []
        loop = asyncio.get_event_loop()
        batch_start_time: float | None = None

        while len(batch) < self.batch_size:
            frame = self.buffer_manager.pop_next_available()

            if frame is not None:
                batch.append(frame)

                if batch_start_time is None:
                    batch_start_time = loop.time()

                continue

            # No frame available right now.
            if batch and batch_start_time is not None:
                elapsed = loop.time() - batch_start_time

                if elapsed >= self.max_wait_seconds:
                    logger.debug(
                        "Emitting partial batch of %d frames after %.2fs wait",
                        len(batch),
                        elapsed,
                    )
                    break

            await asyncio.sleep(self.poll_interval_seconds)

        return batch

    async def run(self, on_batch) -> None:
        """Continuously produce batches and hand each to on_batch.

        on_batch: async callable(list[DecodedFrame]) -> None
        Runs until cancelled.
        """

        try:
            while True:
                batch = await self.next_batch()
                await on_batch(batch)
        except asyncio.CancelledError:
            logger.info("Batcher loop stopped")
            raise