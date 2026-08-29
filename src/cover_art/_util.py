"""Small internal helpers shared across cover_art modules."""

from __future__ import annotations

import re
import threading
import time
from typing import Callable


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "cover"


class Throttle:
    """Enforces a minimum gap between successive wait() calls.

    The interval may be given as a float or a zero-arg callable, read
    fresh on every wait() -- so a caller can retune it at runtime (e.g.
    reassigning a module constant it reads from) and have it take
    effect immediately. Thread-safe: a shared Throttle can be used
    across threads without two waiters both sleeping zero.
    """

    def __init__(self, interval: float | Callable[[], float]) -> None:
        self._interval = interval
        self._last: float | None = None
        self._lock = threading.Lock()

    def wait(self) -> None:
        interval = self._interval() if callable(self._interval) else self._interval
        with self._lock:
            now = time.monotonic()
            if self._last is not None:
                remaining = interval - (now - self._last)
                if remaining > 0:
                    time.sleep(remaining)
                    now = time.monotonic()
            self._last = now
