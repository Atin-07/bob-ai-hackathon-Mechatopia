"""
extract_embedding.py
--------------------
Responsibility:
  1. Crop a face from a frame using a bounding-box dict.
  2. Run ArcFace (via InsightFace buffalo_l) to get a 512-d float embedding.
  3. JPEG-encode the crop and return it as bytes.

The recognition model is loaded ONCE at module import time.

No database, no network calls (beyond the one-time model download that
InsightFace handles internally on first run), no file I/O in the hot path.
"""

from __future__ import annotations

import warnings
from typing import Any

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# One-time model initialisation
# ---------------------------------------------------------------------------
warnings.filterwarnings("ignore")

try:
    from insightface.app import FaceAnalysis

    # Load the full buffalo_l bundle (detector + recogniser).
    # We use both modules here so that InsightFace can do its internal
    # alignment before passing the crop to ArcFace.
    _app: FaceAnalysis = FaceAnalysis(
        name="buffalo_l",
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        # Allow both detection and recognition so ArcFace embedding is
        # available on each Face object.
        allowed_modules=["detection", "recognition"],
    )
    _app.prepare(ctx_id=0, det_size=(640, 640))
    _INSIGHTFACE_AVAILABLE: bool = True

except Exception:  # noqa: BLE001
    _INSIGHTFACE_AVAILABLE = False
    _app = None  # type: ignore[assignment]

# JPEG encoding quality (0-100). 85 is a good balance of size vs quality.
_JPEG_QUALITY: int = 85


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _crop_face(frame: np.ndarray, bbox: dict[str, int]) -> np.ndarray:
    """Return the face crop defined by bbox, clamped to frame dimensions."""
    h_frame, w_frame = frame.shape[:2]

    x = max(0, int(bbox["x"]))
    y = max(0, int(bbox["y"]))
    w = int(bbox["w"])
    h = int(bbox["h"])

    x2 = min(w_frame, x + w)
    y2 = min(h_frame, y + h)

    return frame[y:y2, x:x2]


def _encode_jpeg(crop: np.ndarray) -> bytes:
    """Encode a BGR numpy array to JPEG bytes."""
    ok, buf = cv2.imencode(
        ".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY]
    )
    if not ok or buf is None:
        raise ValueError("Failed to JPEG-encode the face crop.")
    return buf.tobytes()


def _find_best_face(faces: list[Any], bbox: dict[str, int]) -> Any | None:
    """
    Given the list of Face objects returned by InsightFace for the full frame,
    pick the one whose bounding box overlaps most with *bbox*.

    Falls back to the first face if IoU cannot be computed.
    """
    if not faces:
        return None
    if len(faces) == 1:
        return faces[0]

    bx, by, bw, bh = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    bx2, by2 = bx + bw, by + bh

    best_face = None
    best_iou = -1.0

    for face in faces:
        fx1, fy1, fx2, fy2 = face.bbox.astype(int)
        ix1, iy1 = max(bx, fx1), max(by, fy1)
        ix2, iy2 = min(bx2, fx2), min(by2, fy2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = bw * bh + (fx2 - fx1) * (fy2 - fy1) - inter
        iou = inter / union if union > 0 else 0.0
        if iou > best_iou:
            best_iou = iou
            best_face = face

    return best_face


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_embedding(
    frame: np.ndarray,
    bbox: dict[str, int],
) -> dict[str, list[float] | bytes]:
    """
    Crop the face from *frame* using *bbox*, compute a 512-d ArcFace
    embedding, and return the crop as JPEG bytes.

    Parameters
    ----------
    frame : np.ndarray
        Full BGR frame (H×W×3, uint8).
    bbox : dict[str, int]
        Bounding box with keys ``"x"``, ``"y"``, ``"w"``, ``"h"``
        (pixel coordinates, top-left origin).

    Returns
    -------
    dict
        ``{"embedding": list[float], "crop_bytes": bytes}``

        * ``embedding`` — 512-element list of float32 values (L2-normalised
          by InsightFace/ArcFace internally).
        * ``crop_bytes`` — JPEG-encoded bytes of the face crop.

    Raises
    ------
    RuntimeError
        If the InsightFace model is not available.
    ValueError
        If the bbox is degenerate or the crop is empty.
    """
    if not _INSIGHTFACE_AVAILABLE or _app is None:
        raise RuntimeError(
            "InsightFace is not available. Install it with: "
            "pip install insightface onnxruntime"
        )

    if frame is None or frame.size == 0:
        raise ValueError("frame must be a non-empty numpy array.")

    # --- Validate / clamp bbox -----------------------------------------------
    h_frame, w_frame = frame.shape[:2]
    x = max(0, int(bbox["x"]))
    y = max(0, int(bbox["y"]))
    w = int(bbox["w"])
    h = int(bbox["h"])
    x2 = min(w_frame, x + w)
    y2 = min(h_frame, y + h)

    if x2 <= x or y2 <= y:
        raise ValueError(f"Degenerate bounding box after clamping: {bbox}")

    # --- Get JPEG crop (from raw slice, before any alignment) ----------------
    crop_bgr: np.ndarray = frame[y:y2, x:x2]
    crop_bytes: bytes = _encode_jpeg(crop_bgr)

    # --- Run InsightFace on the full frame so alignment is applied properly --
    # InsightFace aligns the face (5-point landmarks → affine warp) before
    # feeding into ArcFace. Cropping first would lose that alignment quality.
    try:
        faces: list[Any] = _app.get(frame)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"InsightFace inference failed: {exc}") from exc

    best = _find_best_face(faces, bbox)

    if best is None or best.embedding is None:
        raise ValueError(
            "InsightFace could not compute an embedding for the given bbox."
        )

    embedding: list[float] = best.embedding.tolist()  # 512 float32s → Python list

    return {
        "embedding": embedding,   # list[float], length 512
        "crop_bytes": crop_bytes, # bytes (JPEG)
    }


# ---------------------------------------------------------------------------
# Combined pipeline (convenience — ties together detect + extract)
# ---------------------------------------------------------------------------

def process_frame(
    frame: np.ndarray,
    camera_id: str,
    organization_id: str,
    pts_ms: float,
) -> list[dict]:
    """
    Full pipeline: detect all faces in *frame*, extract embeddings, return one
    dict per face.

    Parameters
    ----------
    frame : np.ndarray
        BGR video frame (H×W×3, uint8).
    camera_id : str
        Identifier of the camera that produced this frame.
    organization_id : str
        Identifier of the organisation that owns the camera.
    pts_ms : float
        Presentation timestamp of the frame in milliseconds.

    Returns
    -------
    list[dict]
        One entry per detected face::

            {
                "camera_id":       str,
                "organization_id": str,
                "pts_ms":          float,
                "bbox":            {"x": int, "y": int, "w": int, "h": int},
                "embedding":       list[float],   # length 512
                "crop_bytes":      bytes,          # JPEG bytes
            }

        Returns ``[]`` if no faces are found or on any error.
    """
    if not _INSIGHTFACE_AVAILABLE or _app is None:
        return []

    if frame is None or frame.size == 0:
        return []

    # Run detection + recognition in a single pass for efficiency
    try:
        faces: list[Any] = _app.get(frame)
    except Exception:  # noqa: BLE001
        return []

    h_frame, w_frame = frame.shape[:2]
    results: list[dict] = []

    for face in faces:
        if face.embedding is None:
            continue

        # --- Bounding box ---------------------------------------------------
        x1, y1, x2, y2 = face.bbox.astype(int)
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w_frame, x2)
        y2 = min(h_frame, y2)

        bbox_w = x2 - x1
        bbox_h = y2 - y1
        if bbox_w <= 0 or bbox_h <= 0:
            continue

        bbox = {"x": x1, "y": y1, "w": bbox_w, "h": bbox_h}

        # --- Crop → JPEG bytes ----------------------------------------------
        crop_bgr = frame[y1:y2, x1:x2]
        try:
            crop_bytes = _encode_jpeg(crop_bgr)
        except ValueError:
            continue  # skip if encoding fails

        # --- Embedding ------------------------------------------------------
        embedding: list[float] = face.embedding.tolist()

        results.append(
            {
                "camera_id": camera_id,
                "organization_id": organization_id,
                "pts_ms": pts_ms,
                "bbox": bbox,
                "embedding": embedding,
                "crop_bytes": crop_bytes,
            }
        )

    return results
