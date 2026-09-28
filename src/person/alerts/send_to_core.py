import logging

import httpx

from config import settings

logger = logging.getLogger("person_service.send_to_core")


async def send_alert_to_core(alert_data: dict) -> None:
    """
    POSTs the alert to the core service, which pushes it live to a frontend.
    Failures are logged, never raised — a core outage must not crash the
    frame worker or block further processing.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(settings.CORE_ALERT_URL, json=alert_data)
            response.raise_for_status()
    except Exception:
        logger.exception(
            f"Failed to send alert to core for event_id={alert_data.get('event_id')}"
        )