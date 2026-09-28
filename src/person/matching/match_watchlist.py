"""
match_watchlist.py
------------------
Responsibility:
  Compare a single live-camera face embedding against an in-memory watchlist
  of missing / wanted persons and return the closest match (if any).

Public API:
  match_watchlist(
      embedding  : list[float],
      watchlist  : list[dict],
      threshold  : float = 0.4,
  ) -> dict

Constraints (by design):
  - No database access, no SQL, no network calls.
  - The watchlist is handed in already loaded; this module never fetches it.
  - Pure function: no state, no side effects, deterministic output.
  - Only standard library + numpy for the distance calculation.
"""

from __future__ import annotations

import numpy as np  # type: ignore[import-not-found]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine distance between two 1-D float vectors.

    cosine_distance = 1 - cosine_similarity
                    = 1 - (a . b) / (||a|| * ||b||)

    Range: [0, 2].
      0   -> identical direction (perfect match)
      1   -> orthogonal (unrelated)
      2   -> exactly opposite

    ArcFace embeddings are L2-normalised by InsightFace, so ||a|| = ||b|| = 1
    and the dot product alone equals cosine similarity.  We still divide by
    the norms here so the function is safe if a caller supplies unnormalised
    embeddings.

    Parameters
    ----------
    a, b : np.ndarray
        1-D float arrays of the same length.

    Returns
    -------
    float
        Cosine distance in [0, 2].
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0.0 or norm_b == 0.0:
        # A zero vector has no direction; treat as maximally dissimilar.
        return 2.0

    cosine_sim: float = float(np.dot(a, b) / (norm_a * norm_b))
    # Clamp to [-1, 1] to guard against floating-point rounding past 1.0
    cosine_sim = max(-1.0, min(1.0, cosine_sim))
    return 1.0 - cosine_sim


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_watchlist(
    embedding: list[float],
    watchlist: list[dict],
    threshold: float = 0.4,
) -> dict:
    """
    Compare *embedding* against every entry in *watchlist* and return the
    closest match if its cosine distance is below *threshold*.

    Distance metric
    ---------------
    cosine_distance = 1 - cosine_similarity

    Typical ArcFace operating points (buffalo_l):
      < 0.30  -> very confident match
      0.30 - 0.40  -> likely match (default threshold sits here)
      > 0.40  -> different person

    The default threshold of 0.4 is a sensible starting point but should be
    tuned on a held-out validation set for the specific deployment.

    Parameters
    ----------
    embedding : list[float]
        512-element face embedding extracted from a live camera frame, as
        returned by extract_embedding.py or embed_reference.py.

    watchlist : list[dict]
        In-memory watchlist, each entry shaped::

            {
                "person_id":          str,
                "name":               str,
                "category":           "missing" | "wanted",
                "reference_embedding": list[float],   # 512 floats
            }

        Entries with a missing or non-512-length reference_embedding are
        skipped with a warning rather than raising an exception, so one bad
        record does not block the rest.

    threshold : float, optional
        Cosine distance cutoff (default 0.4).  A candidate is considered a
        match only when its distance is *strictly less than* this value.
        Lower values are stricter (fewer false positives, more false negatives).

    Returns
    -------
    dict
        If a match is found::

            {
                "matched":         True,
                "person_id":       str,
                "name":            str,
                "category":        str,   # "missing" | "wanted"
                "similarity_score": float, # cosine similarity in [0, 1]
            }

        If no match is found::

            {"matched": False}

    Raises
    ------
    ValueError
        If *embedding* is not a 512-element list / array.

    Notes
    -----
    Watchlist sizes are expected to be small (tens to a few hundred entries).
    A vectorised numpy comparison is used for efficiency, falling back to a
    per-entry loop for entries that cannot be stacked (e.g. bad shapes).

    Examples
    --------
    >>> from match_watchlist import match_watchlist
    >>> result = match_watchlist(live_emb, watchlist)
    >>> if result["matched"]:
    ...     print(f"ALERT: matched {result['name']} ({result['category']})")
    """
    # --- Validate the probe embedding ----------------------------------------
    probe = np.asarray(embedding, dtype=np.float64)
    if probe.ndim != 1 or probe.shape[0] != 512:
        raise ValueError(
            f"embedding must be a flat 512-element vector, "
            f"got shape {probe.shape}."
        )

    if not watchlist:
        return {"matched": False}

    # --- Build a matrix of reference embeddings for vectorised comparison ----
    # We try to stack all valid entries at once; invalid rows are tracked so
    # we can map distances back to person records.

    valid_entries: list[dict] = []
    ref_rows: list[np.ndarray] = []

    for entry in watchlist:
        ref_emb = entry.get("reference_embedding")
        if ref_emb is None:
            import warnings
            warnings.warn(
                f"Watchlist entry '{entry.get('person_id', '?')}' has no "
                "'reference_embedding'; skipping.",
                stacklevel=2,
            )
            continue

        ref_arr = np.asarray(ref_emb, dtype=np.float64)
        if ref_arr.ndim != 1 or ref_arr.shape[0] != 512:
            import warnings
            warnings.warn(
                f"Watchlist entry '{entry.get('person_id', '?')}' has an "
                f"unexpected embedding shape {ref_arr.shape}; skipping.",
                stacklevel=2,
            )
            continue

        valid_entries.append(entry)
        ref_rows.append(ref_arr)

    if not valid_entries:
        return {"matched": False}

    # Stack into (N, 512) matrix
    ref_matrix = np.stack(ref_rows, axis=0)  # shape: (N, 512)

    # --- Vectorised cosine distance ------------------------------------------
    # ArcFace embeddings are L2-normalised, but we normalise explicitly here
    # so the function is robust to unnormalised inputs.

    probe_norm = np.linalg.norm(probe)
    ref_norms = np.linalg.norm(ref_matrix, axis=1)  # shape: (N,)

    # Replace zero norms with 1 to avoid division by zero; those entries will
    # produce a dot product of 0 and a distance of 1 (correctly dissimilar).
    ref_norms_safe = np.where(ref_norms == 0.0, 1.0, ref_norms)
    probe_norm_safe = probe_norm if probe_norm != 0.0 else 1.0

    # Dot products of probe against every reference: shape (N,)
    dot_products = ref_matrix @ probe  # equivalent to (ref_matrix @ probe.T)

    cosine_sims = dot_products / (ref_norms_safe * probe_norm_safe)
    cosine_sims = np.clip(cosine_sims, -1.0, 1.0)  # guard rounding errors

    distances = 1.0 - cosine_sims  # shape: (N,), cosine distances in [0, 2]

    # --- Find the closest entry ----------------------------------------------
    best_idx: int = int(np.argmin(distances))
    best_distance: float = float(distances[best_idx])
    best_similarity: float = float(cosine_sims[best_idx])

    if best_distance < threshold:
        matched_entry = valid_entries[best_idx]
        return {
            "matched": True,
            "person_id": matched_entry["person_id"],
            "name": matched_entry["name"],
            "category": matched_entry["category"],
            # similarity_score: cosine similarity in [0, 1] (higher = closer)
            "similarity_score": round(best_similarity, 6),
        }

    return {"matched": False}