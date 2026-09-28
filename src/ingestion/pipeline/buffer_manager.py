"""Per-camera bounded frame buffers.

Each camera gets its own bounded queue -- never one shared queue across all
cameras -- so a slow or dead camera can't consume unbounded memory or starve
other cameras. When a camera's buffer is full, the oldest frame is dropped
to make room for the newest one (prefer fresh frames over unlimited latency).
"""

import logging
from collections import deque

from pipeline.decoder import DecodedFrame

logger = logging.getLogger("buffer_manager")


class CameraBuffer:
    """A bounded, drop-oldest FIFO buffer for a single camera's frames."""

    def __init__(self, camera_id: str, max_size: int):
        self.camera_id = camera_id
        self.max_size = max_size
        self._queue: deque[DecodedFrame] = deque()
        self._dropped_count = 0

    def push(self, frame: DecodedFrame) -> None:
        """Add a frame, dropping the oldest one first if buffer is full."""

        if len(self._queue) >= self.max_size:
            self._queue.popleft()
            self._dropped_count += 1

            if self._dropped_count % 50 == 0:
                logger.warning(
                    "%s: buffer full, dropped %d frames so far (consumer "
                    "may be falling behind)",
                    self.camera_id,
                    self._dropped_count,
                )

        self._queue.append(frame)

    def pop(self) -> DecodedFrame | None:
        """Remove and return the oldest frame, or None if empty."""

        if not self._queue:
            return None

        return self._queue.popleft()

    def __len__(self) -> int:
        return len(self._queue)

    def is_empty(self) -> bool:
        return len(self._queue) == 0

    @property
    def dropped_count(self) -> int:
        return self._dropped_count


class BufferManager:
    """Owns one CameraBuffer per active camera and provides round-robin
    access across all of them for the batcher to pull from.
    """

    def __init__(self, max_size_per_camera: int):
        self.max_size_per_camera = max_size_per_camera
        self._buffers: dict[str, CameraBuffer] = {}
        self._round_robin_order: list[str] = []
        self._round_robin_index = 0

    def ensure_camera(self, camera_id: str) -> None:
        """Create a buffer for camera_id if one doesn't already exist."""

        if camera_id not in self._buffers:
            self._buffers[camera_id] = CameraBuffer(camera_id, self.max_size_per_camera)
            self._round_robin_order.append(camera_id)
            logger.info("%s: buffer created (max_size=%d)", camera_id, self.max_size_per_camera)

    def remove_camera(self, camera_id: str) -> None:
        """Drop a camera's buffer entirely (e.g. camera went offline)."""

        if camera_id in self._buffers:
            del self._buffers[camera_id]
            self._round_robin_order.remove(camera_id)
            logger.info("%s: buffer removed", camera_id)


    def active_camera_ids(self) -> list[str]:
        """Camera IDs that currently have a buffer (public, safe accessor —
        avoids callers reaching into the private _buffers dict directly).
        """

        return list(self._buffers.keys())

    def push(self, frame: DecodedFrame) -> None:
        """Push a frame into its camera's buffer, creating the buffer if needed."""

        self.ensure_camera(frame.camera_id)
        self._buffers[frame.camera_id].push(frame)

    def pop_next_available(self) -> DecodedFrame | None:
        """Pop one frame using round-robin across all cameras with pending
        frames, so no single camera dominates batch composition.
        """

        if not self._round_robin_order:
            return None

        num_cameras = len(self._round_robin_order)

        for _ in range(num_cameras):
            self._round_robin_index %= len(self._round_robin_order)
            camera_id = self._round_robin_order[self._round_robin_index]
            self._round_robin_index += 1

            buffer = self._buffers.get(camera_id)

            if buffer is not None and not buffer.is_empty():
                return buffer.pop()

        return None

    def total_pending(self) -> int:
        return sum(len(buffer) for buffer in self._buffers.values())

    def stats(self) -> dict[str, dict[str, int]]:
        """Per-camera pending/dropped counts, useful for health.py."""

        return {
            camera_id: {
                "pending": len(buffer),
                "dropped": buffer.dropped_count,
            }
            for camera_id, buffer in self._buffers.items()
        }