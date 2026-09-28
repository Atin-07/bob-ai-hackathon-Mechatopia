from typing import Optional

from .decoder import DecodedFrame


class FrameSampler:
    """
    Selects frames from a live camera stream using PTS.

    Example:
        target_fps = 5

        30 FPS camera
            ↓
        PTS-based sampler
            ↓
        approximately 5 selected frames/sec
    """

    def __init__(self, target_fps: float = 5.0):
        if target_fps <= 0:
            raise ValueError("target_fps must be greater than 0")

        self.target_interval_ms = 1000.0 / target_fps

        # Last PTS that was accepted.
        self.last_selected_pts_ms: Optional[float] = None

    def should_select(self, frame: DecodedFrame) -> bool:
        """
        Decide whether this frame should be selected.

        Timing is based entirely on the frame's PTS.
        """

        pts_ms = frame.pts_ms

        # First frame is always selected.
        if self.last_selected_pts_ms is None:
            self.last_selected_pts_ms = pts_ms
            return True

        elapsed_ms = pts_ms - self.last_selected_pts_ms

        # Ignore invalid/non-monotonic timestamps.
        if elapsed_ms <= 0:
            return False

        if elapsed_ms >= self.target_interval_ms:
            self.last_selected_pts_ms = pts_ms
            return True

        return False

    def reset(self):
        """
        Reset sampler state.

        Useful after a camera reconnect or scene discontinuity.
        """

        self.last_selected_pts_ms = None