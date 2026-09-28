import time
import threading


class CooldownTracker:
    """
    Simple in-memory cooldown tracker keyed by (camera_id, person_id).
    Prevents re-alerting on the same person at the same camera within
    ALERT_COOLDOWN_SECONDS. Thread-safe with a basic lock since asyncio
    tasks can interleave; cheap enough not to matter for hackathon scale.
    """

    def __init__(self, cooldown_seconds: int = 60):
        self.cooldown_seconds = cooldown_seconds
        self._last_alerted: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def is_on_cooldown(self, camera_id: str, person_id: str) -> bool:
        key = (camera_id, person_id)
        with self._lock:
            last = self._last_alerted.get(key)
            if last is None:
                return False
            return (time.monotonic() - last) < self.cooldown_seconds

    def record_alert(self, camera_id: str, person_id: str) -> None:
        key = (camera_id, person_id)
        with self._lock:
            self._last_alerted[key] = time.monotonic()