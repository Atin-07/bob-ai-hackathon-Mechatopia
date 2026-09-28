"""Encodes raw decoded frames to JPEG -- and only at this final boundary,
right before dispatch to Vehicle AI / Face AI. Nothing upstream (decode,
sample, buffer, batch) ever touches JPEG or base64, per the pipeline's
raw-frame-internally contract.
"""

import logging

import cv2

from pipeline.decoder import DecodedFrame

logger = logging.getLogger("frame_encoder")

_DEFAULT_JPEG_QUALITY = 85


class EncodedFrame:
    """A frame encoded to JPEG bytes, ready for dispatch."""

    def __init__(
        self,
        camera_id: str,
        organization_id: str,
        pts_ms: float,
        width: int,
        height: int,
        jpeg_bytes: bytes,
        format: str = "jpeg",
    ):
        self.camera_id = camera_id
        self.organization_id = organization_id
        self.pts_ms = pts_ms
        self.width = width
        self.height = height
        self.jpeg_bytes = jpeg_bytes
        self.format = format


def encode_frame(frame: DecodedFrame, quality: int = _DEFAULT_JPEG_QUALITY) -> EncodedFrame | None:
    """Encode a single raw DecodedFrame to JPEG.

    Returns None (and logs) if encoding fails rather than raising, so one
    bad frame doesn't crash an entire batch's dispatch.
    """

    success, buffer = cv2.imencode(
        ".jpg", frame.data, [cv2.IMWRITE_JPEG_QUALITY, quality]
    )

    if not success:
        logger.warning(
            "%s: failed to JPEG-encode frame at pts=%.0f",
            frame.camera_id,
            frame.pts_ms,
        )
        return None

    return EncodedFrame(
        camera_id=frame.camera_id,
        organization_id=frame.organization_id,
        pts_ms=frame.pts_ms,
        width=frame.width,
        height=frame.height,
        jpeg_bytes=buffer.tobytes(),
    )


def encode_batch(frames: list[DecodedFrame], quality: int = _DEFAULT_JPEG_QUALITY) -> list[EncodedFrame]:
    """Encode a batch of frames, silently dropping any that fail to encode."""

    encoded = []

    for frame in frames:
        result = encode_frame(frame, quality)
        if result is not None:
            encoded.append(result)

    return encoded