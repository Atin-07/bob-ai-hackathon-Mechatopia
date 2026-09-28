"""RTSP stream decoding into raw frames, driven entirely by PTS.

Uses OpenCV/FFmpeg with RTSP forced over TCP. PTS comes from
cv2.CAP_PROP_POS_MSEC -- never from frame arrival time and never from
CAP_PROP_FPS, since neither is reliable per the Sentinel grid guide.
"""

import logging
import os
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger("decoder")

# Must be set before any cv2.VideoCapture(..., cv2.CAP_FFMPEG) call.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")


@dataclass
class DecodedFrame:
    """A single raw decoded frame with its true stream PTS."""

    camera_id: str
    organization_id: str
    pts_ms: float
    width: int
    height: int
    pixel_format: str
    data: np.ndarray  # raw BGR frame buffer, undecoded further (no JPEG/base64)


class StreamDecoder:
    """Wraps a single RTSP capture and yields DecodedFrame objects.

    One instance = one camera = one RTSP connection. Does not handle
    reconnect/backoff itself -- that's stream_manager.py's job, which
    creates/destroys StreamDecoder instances as connections drop and
    are re-established.
    """

    def __init__(self, camera_id: str, organization_id: str, rtsp_url: str):
        self.camera_id = camera_id
        self.organization_id = organization_id
        self.rtsp_url = rtsp_url
        self._cap: cv2.VideoCapture | None = None
        self._last_pts_ms: float | None = None

    def open(self) -> bool:
        """Open the RTSP connection. Returns True on success."""

        self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

        if not self._cap.isOpened():
            logger.warning(
                "Failed to open stream for %s at %s", self.camera_id, self.rtsp_url
            )
            self._cap = None
            return False

        logger.info("Opened RTSP stream for %s", self.camera_id)
        self._last_pts_ms = None
        return True

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read_frame(self) -> DecodedFrame | None:
        """Read one decoded frame.

        Returns None if the read failed (caller should treat this as a
        signal to trigger reconnect logic upstream in stream_manager.py).
        Decoder-level stderr warnings on join (e.g. missing IDR/POC refs)
        are emitted by the underlying FFmpeg backend directly and are not
        surfaced here as exceptions -- they are expected and self-correct
        once the first keyframe arrives. Only an actual failed read() is
        treated as a real problem.
        """

        if self._cap is None:
            return None

        ok, frame = self._cap.read()

        if not ok or frame is None:
            return None

        pts_ms = self._cap.get(cv2.CAP_PROP_POS_MSEC)

        # Some backends report 0 or a non-monotonic value transiently right
        # after connecting (buffered GOP replay). Do not fabricate a PTS --
        # pass it through as-is; the sampler is responsible for rejecting
        # non-monotonic values.
        height, width = frame.shape[:2]

        self._last_pts_ms = pts_ms

        return DecodedFrame(
            camera_id=self.camera_id,
            organization_id=self.organization_id,
            pts_ms=pts_ms,
            width=width,
            height=height,
            pixel_format="BGR",
            data=frame,
        )

    def close(self) -> None:
        """Release the underlying capture."""

        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Closed RTSP stream for %s", self.camera_id)

    def reset_for_discontinuity(self) -> None:
        """Reset local decoder state after a detected scene discontinuity.

        Does not reopen the connection -- just clears state that assumed
        continuity (e.g. last-seen PTS), since the underlying feed loops
        and cuts abruptly at the loop point.
        """

        self._last_pts_ms = None
        logger.info("Reset decoder state for %s after scene discontinuity", self.camera_id)