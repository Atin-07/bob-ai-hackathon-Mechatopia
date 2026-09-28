"""Builds the exact JSON batch payload expected by Vehicle AI / Face AI
from a list of EncodedFrame objects. The same payload dict is sent to
both consumers -- the pipeline does not know or care what they do with it.
"""

import base64
from typing import List

from .frame_encoder import EncodedFrame


class PayloadBuilder:
    """Builds the batch payload sent to Vehicle AI / Face AI."""

    def build(self, frames: List[EncodedFrame]) -> dict:
        """Convert a batch of encoded frames into the agreed JSON shape.

        jpeg_bytes is base64-encoded here because raw bytes cannot be
        embedded directly in a JSON body (httpx's json= will fail on
        bytes) -- this is the one point where binary data crosses into
        the JSON contract the AI teams gave us.
        """

        payload = {"frames": []}

        for encoded_frame in frames:
            frame_data = {
                "camera_id": encoded_frame.camera_id,
                "organization_id": encoded_frame.organization_id,
                "pts_ms": encoded_frame.pts_ms,
                "width": encoded_frame.width,
                "height": encoded_frame.height,
                "format": encoded_frame.format,
                "frame": base64.b64encode(encoded_frame.jpeg_bytes).decode("ascii"),
            }
            payload["frames"].append(frame_data)

        return payload