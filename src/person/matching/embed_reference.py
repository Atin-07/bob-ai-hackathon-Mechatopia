"""
embed_reference.py
------------------
Responsibility:
  Produce a 512-dimensional ArcFace embedding for a single reference photo
  (e.g. an admin-uploaded photo of a missing or wanted person).

  The InsightFace buffalo_l model is loaded ONCE at module import time and
  reused across all calls -- identical approach to extract_embedding.py so
  that all embeddings in the system are produced by the same model weights
  and are therefore directly comparable.

Public API:
  embed_reference_photo(image: np.ndarray) -> list[float]

Constraints (by design):
  - No database access.
  - No network calls in the hot path (the one-time model download on first
    run is handled internally by InsightFace).
  - No file I/O.
  - Pure function: same input -> same output, no side effects.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# One-time model initialisation (mirrors extract_embedding.py)
# ---------------------------------------------------------------------------
warnings.filterwarnings("ignore")

try:
    from insightface.app import FaceAnalysis  # type: ignore[import-untyped]

    # buffalo_l bundles both the RetinaFace detector and the ArcFace
    # recogniser.  We need both so InsightFace can perform its internal
    # 5-point landmark alignment before feeding the crop into ArcFace --
    # the same pipeline used in extract_embedding.py for live frames.
    _app: FaceAnalysis = FaceAnalysis(
        name="buffalo_l",
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        allowed_modules=["detection", "recognition"],
    )
    _app.prepare(ctx_id=0, det_size=(640, 640))
    _INSIGHTFACE_AVAILABLE: bool = True

except Exception:  # noqa: BLE001
    _INSIGHTFACE_AVAILABLE = False
    _app = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def embed_reference_photo(image: np.ndarray) -> list[float]:
    """
    Compute a 512-dimensional ArcFace embedding for a single reference photo.

    The function assumes there is exactly one clear, forward-facing face in
    the image (e.g. an ID photo or a clear photo uploaded by an admin).
    If InsightFace detects multiple faces it uses the one with the highest
    detection confidence score.  If no face is detected an error is raised
    so the caller knows the reference photo is unusable.

    Parameters
    ----------
    image : np.ndarray
        BGR image as a NumPy array (H x W x 3, uint8), the same format
        returned by cv2.imread or any OpenCV capture.  The caller is
        responsible for loading the image; this function does no file I/O.

    Returns
    -------
    list[float]
        A 512-element list of float32 values.  The vector is L2-normalised
        internally by InsightFace/ArcFace, so it is unit-length and ready
        for cosine-distance comparison via match_watchlist.py.

    Raises
    ------
    RuntimeError
        If the InsightFace model failed to load at import time.
    ValueError
        If image is None / empty, or if no face can be detected in it.

    Examples
    --------
    >>> import cv2
    >>> from embed_reference import embed_reference_photo
    >>> img = cv2.imread("missing_person.jpg")
    >>> emb = embed_reference_photo(img)
    >>> len(emb)
    512
    """
    if not _INSIGHTFACE_AVAILABLE or _app is None:
        raise RuntimeError(
            "InsightFace is not available. "
            "Install it with: pip install insightface onnxruntime"
        )

    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError(
            "image must be a non-empty NumPy array (BGR, H x W x 3, uint8)."
        )

    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(
            f"Expected a 3-channel BGR image, got shape {image.shape}."
        )

    # Run detection + recognition (with landmark alignment) on the full image.
    try:
        faces: list[Any] = _app.get(image)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"InsightFace inference failed on the reference image: {exc}"
        ) from exc

    if not faces:
        raise ValueError(
            "No face detected in the reference photo. "
            "Please provide a clear, unobstructed photo with exactly one face."
        )

    # Pick the face with the highest detection confidence.
    # For a well-cropped reference photo this will always be the only face,
    # but being robust here costs nothing.
    best_face: Any = max(faces, key=lambda f: float(f.det_score))

    if best_face.embedding is None:
        raise ValueError(
            "InsightFace detected a face but could not compute an embedding. "
            "The face may be too small, blurry, or at an extreme angle."
        )

    # .tolist() converts float32 ndarray -> plain Python list[float]
    embedding: list[float] = best_face.embedding.tolist()  # length 512

    return embedding