# This Script is responsible for throttling outgoing requests to the Model Provider to a fixed rate
# Token-bucket limiter: allows short bursts up to the bucket's capacity, then spaces requests out
# to the configured steady-state rate. acquire() is BLOCKING by design -- it sleeps the calling
# thread until a token is available, since ModelClient.post() is a synchronous call and there's
# no async request path in this project.
#
# IMPORTANT: this only throttles anything if the SAME RateLimiter instance is shared across every
# ModelClient that talks to the provider. ModelClient is constructed fresh per turn (and again by
# Summarizer for its own calls) -- a rate limiter created per-instance would reset its bucket every
# single call and throttle nothing. `default_rate_limiter` below exists so every call site shares
# one bucket without each caller having to be wired to pass one through explicitly.
import threading
import time
from src.core.config import RATE_LIMIT_RPM


class RateLimiter:
    """
    Thread-safe token bucket. Safe to share one instance across multiple
    threads -- the lock only serializes token accounting (a few microseconds),
    not the request itself, so it doesn't hold up unrelated work.
    """

    def __init__(self, requests_per_minute: int = RATE_LIMIT_RPM) -> None:
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        self.capacity = requests_per_minute
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Blocks the calling thread until a token is available, then consumes one."""
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                wait_time = (1 - self._tokens) / self.refill_rate
            time.sleep(wait_time)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now


# Shared across every ModelClient by default -- see module docstring above for why
# a per-instance limiter would be a no-op given how ModelClient is constructed.
default_rate_limiter = RateLimiter()
