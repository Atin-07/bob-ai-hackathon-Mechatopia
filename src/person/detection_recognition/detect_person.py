"""
detect_person.py
----------------
Responsibility: detect faces in a BGR numpy frame and return bounding boxes.

Model (buffalo_l via InsightFace) is loaded ONCE at module import time so it
is never reloaded on subsequent calls — safe for a live per-frame pipeline.

No database, no network calls, no file I/O beyond the one-time model load
that InsightFace handles internally.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# One-time model initialisation
# ---------------------------------------------------------------------------
# We suppress verbose logs from InsightFace/onnxruntime here.
warnings.filterwarnings("ignore")

try:
    import insightface
    from insightface.app import FaceAnalysis

    _app: FaceAnalysis = FaceAnalysis(
        name="buffalo_l",
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        allowed_modules=["detection"],   # only the detector — skip recognition
    )
    # det_size=(640, 640) gives good accuracy; lower it (e.g. 320) if CPU is
    # too slow.
    _app.prepare(ctx_id=0, det_size=(640, 640))
    _INSIGHTFACE_AVAILABLE: bool = True

except Exception:  # noqa: BLE001
    _INSIGHTFACE_AVAILABLE = False
    _app = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_faces(frame: np.ndarray) -> list[dict[str, int]]:
    """
    Run face detection on a single BGR frame.

    Parameters
    ----------
    frame : np.ndarray
        BGR image array as returned by OpenCV (shape H×W×3, dtype uint8).

    Returns
    -------
    list[dict[str, int]]
        A list of bounding-box dicts, one per detected face::

            [{"x": int, "y": int, "w": int, "h": int}, ...]

        Returns an empty list when no faces are found or if the model is
        unavailable (never raises).
    """
    if frame is None or frame.size == 0:
        return []

    if not _INSIGHTFACE_AVAILABLE or _app is None:
        return []

    try:
        faces: list[Any] = _app.get(frame)
    except Exception:  # noqa: BLE001
        return []

    bboxes: list[dict[str, int]] = []
    for face in faces:
        # InsightFace bbox is [x1, y1, x2, y2] as float32
        x1, y1, x2, y2 = face.bbox.astype(int)

        # Clamp to frame boundaries
        h_frame, w_frame = frame.shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w_frame, x2)
        y2 = min(h_frame, y2)

        w = x2 - x1
        h = y2 - y1

        if w <= 0 or h <= 0:
            continue  # skip degenerate boxes

        bboxes.append({"x": x1, "y": y1, "w": w, "h": h})

    return bboxes
