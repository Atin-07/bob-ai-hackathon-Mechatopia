"""
Service-to-service authentication only.
verify_service_key is used by the ingestion service's GLS sync endpoint.
"""

import os
from typing import Optional

from fastapi import Header, HTTPException, status

SERVICE_KEY = os.getenv("SERVICE_KEY", "netra-service-key-2024")


def verify_service_key(x_service_key: Optional[str] = Header(None)) -> None:
    if x_service_key != SERVICE_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Service-Key",
        )
