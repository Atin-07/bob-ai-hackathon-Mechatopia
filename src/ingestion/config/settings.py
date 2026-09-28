"""Central configuration for the ingestion pipeline.

All values are overridable via environment variables (see .env.example).
Nothing here should be hardcoded elsewhere in the pipeline — every tunable
(fps, batch size, stream limits, backoff timing, endpoints) lives here.
"""

import os
from functools import lru_cache

from pydantic import BaseModel


def _get_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _get_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


def _get_float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


class Settings(BaseModel):
    """Runtime configuration, loaded once from environment variables."""

    # --- Catalogue ---
    catalogue_base_url: str = _get_str("CATALOGUE_BASE_URL", "http://localhost:8000")
    catalogue_refresh_interval_seconds: float = _get_float(
        "CATALOGUE_REFRESH_INTERVAL_SECONDS", 30.0
    )
    catalogue_timeout_seconds: float = _get_float("CATALOGUE_TIMEOUT_SECONDS", 5.0)

    # --- Stream connection ---
    rtsp_transport: str = _get_str("RTSP_TRANSPORT", "tcp")
    max_active_streams: int = _get_int("MAX_ACTIVE_STREAMS", 10)

    # --- Reconnect / backoff ---
    reconnect_initial_backoff_seconds: float = _get_float(
        "RECONNECT_INITIAL_BACKOFF_SECONDS", 2.0
    )
    reconnect_max_backoff_seconds: float = _get_float(
        "RECONNECT_MAX_BACKOFF_SECONDS", 30.0
    )

    # --- Sampling ---
    target_sample_fps: float = _get_float("TARGET_SAMPLE_FPS", 5.0)

    # --- Per-camera buffering ---
    camera_buffer_max_size: int = _get_int("CAMERA_BUFFER_MAX_SIZE", 30)

    # --- Batching ---
    batch_size: int = _get_int("BATCH_SIZE", 4)
    batch_max_wait_seconds: float = _get_float("BATCH_MAX_WAIT_SECONDS", 1.0)

    # --- Dispatch: Vehicle AI / Face AI ---
    vehicle_ai_url: str = _get_str("VEHICLE_AI_URL", "http://localhost:9001/process")
    face_ai_url: str = _get_str("FACE_AI_URL", "http://localhost:8001/person/batch")
    dispatch_timeout_seconds: float = _get_float("DISPATCH_TIMEOUT_SECONDS", 5.0)
    dispatch_queue_max_size: int = _get_int("DISPATCH_QUEUE_MAX_SIZE", 50)

    # --- GLS registry ---
    gls_registry_url: str = _get_str("GLS_REGISTRY_URL", "http://localhost:8000/cameras/gls-sync")
    gls_push_interval_seconds: float = _get_float("GLS_PUSH_INTERVAL_SECONDS", 30.0)
    service_key: str = _get_str("SERVICE_KEY", "shared-secret-agree-with-teammate")

    # --- Server (for our own mock /api/ingest + health) ---
    server_host: str = _get_str("SERVER_HOST", "0.0.0.0")
    server_port: int = _get_int("SERVER_PORT", 8000)

    # --- Logging ---
    log_level: str = _get_str("LOG_LEVEL", "INFO")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings singleton."""

    return Settings()

