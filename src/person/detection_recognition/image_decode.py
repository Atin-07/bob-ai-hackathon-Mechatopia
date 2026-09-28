"""
image_decode.py
---------------
Responsibility: convert a base64-encoded JPEG string into a BGR numpy array.

No model loading, no I/O, no network calls.
"""

import base64
from typing import Optional

import cv2
import numpy as np


def decode_frame(base64_string: str) -> np.ndarray:
    """
    Decode a base64-encoded JPEG string into a BGR numpy array.

    Parameters
    ----------
    base64_string : str
        A standard base64-encoded JPEG image (with or without the
        "data:image/jpeg;base64," prefix — the prefix is stripped
        automatically if present).

    Returns
    -------
    np.ndarray
        Decoded image in BGR format, shape (H, W, 3), dtype uint8.

    Raises
    ------
    ValueError
        If the bytes cannot be decoded to a valid image.
    """
    # Strip optional data-URI prefix (e.g. "data:image/jpeg;base64,...")
    if "," in base64_string:
        base64_string = base64_string.split(",", 1)[1]

    raw_bytes: bytes = base64.b64decode(base64_string)
    byte_array = np.frombuffer(raw_bytes, dtype=np.uint8)
    frame: Optional[np.ndarray] = cv2.imdecode(byte_array, cv2.IMREAD_COLOR)

    if frame is None:
        raise ValueError(
            "cv2.imdecode returned None — the provided bytes are not a valid "
            "JPEG/image."
        )

    return frame
