"""In-memory sliding window rate limiter per customer phone number."""

import time
from collections import defaultdict


class CustomerRateLimiter:
    """Sliding-window in-memory rate limiter per customer phone."""

    def __init__(self, max_requests: int = 20, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, phone: str) -> bool:
        """Check if request is within rate limit; record timestamp if allowed."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        timestamps = self._history[phone]

        # Prune expired timestamps
        self._history[phone] = [ts for ts in timestamps if ts > cutoff]

        if len(self._history[phone]) >= self.max_requests:
            return False

        self._history[phone].append(now)
        return True

    def reset(self, phone: str | None = None) -> None:
        """Reset history for a specific phone or all phones."""
        if phone:
            self._history.pop(phone, None)
        else:
            self._history.clear()


# Global singleton rate limiter
customer_rate_limiter = CustomerRateLimiter(max_requests=20, window_seconds=60.0)
