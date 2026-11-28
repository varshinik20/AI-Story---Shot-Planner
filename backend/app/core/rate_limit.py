import asyncio
from collections import defaultdict, deque
import math
import time

from fastapi import Request

from app.core.exceptions import RateLimitExceededError


class LoginRateLimiter:
    """Thread-safe sliding-window in-memory rate limiter for login attempts by client IP."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300) -> None:
        self._max_attempts = max(1, max_attempts)
        self._window_seconds = max(1, window_seconds)
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    def _prune_unlocked(self, key: str, now: float) -> deque[float]:
        bucket = self._attempts[key]
        cutoff = now - self._window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        return bucket

    async def check_allowed(self, key: str) -> None:
        """Raise RateLimitExceededError if client key exceeded max attempts in current window."""
        async with self._lock:
            now = time.monotonic()
            bucket = self._prune_unlocked(key, now)
            if len(bucket) >= self._max_attempts:
                retry_after = max(1, math.ceil(self._window_seconds - (now - bucket[0])))
                raise RateLimitExceededError(
                    message="Too many login attempts. Please try again later.",
                    retry_after_seconds=retry_after,
                )

    async def record_failure(self, key: str) -> None:
        """Record a failed login attempt for the given client key."""
        async with self._lock:
            now = time.monotonic()
            bucket = self._prune_unlocked(key, now)
            bucket.append(now)

    async def reset(self, key: str | None = None) -> None:
        """Clear attempts for a specific key on success, or all keys in tests."""
        async with self._lock:
            if key is None:
                self._attempts.clear()
            else:
                self._attempts.pop(key, None)


def extract_client_ip(request: Request) -> str:
    """Resolve client IP safely from proxy header or socket peer."""
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
