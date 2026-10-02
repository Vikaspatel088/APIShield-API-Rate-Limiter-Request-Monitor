from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Deque, Dict, Literal

from app.models import RateLimitDecision


AlgorithmName = Literal['fixed_window', 'sliding_window', 'token_bucket']


@dataclass
class BucketState:
    count: int = 0
    window_start: float = 0.0
    last_refill: float = 0.0
    tokens: float = 0.0


class FixedWindowStrategy:
    def __init__(self) -> None:
        self._buckets: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        with self._lock:
            return self._allow(key, limit, window_seconds)

    def _allow(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = time.monotonic()
        current_window = int(now // window_seconds)
        bucket_key = f'{key}:{current_window}'
        state = self._buckets.get(bucket_key, {'count': 0})
        count = int(state['count'])

        if count >= limit:
            reset_at = (current_window + 1) * window_seconds
            retry_after = max(0.0, reset_at - now)
            return RateLimitDecision(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after=retry_after,
                reset_at=reset_at,
                reason='fixed_window_limit_exceeded',
            )

        state['count'] = count + 1
        self._buckets[bucket_key] = state
        remaining = max(0, limit - (count + 1))
        return RateLimitDecision(
            allowed=True,
            limit=limit,
            remaining=remaining,
            retry_after=0.0,
            reset_at=(current_window + 1) * window_seconds,
            reason=None,
        )


class SlidingWindowStrategy:
    def __init__(self) -> None:
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        with self._lock:
            return self._allow(key, limit, window_seconds)

    def _allow(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = time.monotonic()
        window = self._requests[key]
        cutoff = now - window_seconds
        while window and window[0] <= cutoff:
            window.popleft()

        if len(window) >= limit:
            oldest = window[0]
            retry_after = max(0.0, (oldest + window_seconds) - now)
            return RateLimitDecision(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after=retry_after,
                reset_at=oldest + window_seconds,
                reason='sliding_window_limit_exceeded',
            )

        window.append(now)
        remaining = max(0, limit - len(window))
        reset_at = window[0] + window_seconds if window else now + window_seconds
        return RateLimitDecision(
            allowed=True,
            limit=limit,
            remaining=remaining,
            retry_after=0.0,
            reset_at=reset_at,
            reason=None,
        )


class TokenBucketStrategy:
    def __init__(self) -> None:
        self._buckets: Dict[str, BucketState] = {}
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        with self._lock:
            return self._allow(key, limit, window_seconds)

    def _allow(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = time.monotonic()
        state = self._buckets.setdefault(key, BucketState(tokens=float(limit), last_refill=now))
        elapsed = max(0.0, now - state.last_refill)
        refill_rate = limit / float(window_seconds)
        state.tokens = min(float(limit), state.tokens + elapsed * refill_rate)
        state.last_refill = now

        if state.tokens < 1.0:
            wait_time = (1.0 - state.tokens) / refill_rate if refill_rate > 0 else 0.0
            return RateLimitDecision(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after=max(0.0, wait_time),
                reset_at=now + wait_time,
                reason='token_bucket_limit_exceeded',
            )

        state.tokens -= 1.0
        remaining = max(0, math.floor(state.tokens))
        return RateLimitDecision(
            allowed=True,
            limit=limit,
            remaining=remaining,
            retry_after=0.0,
            reset_at=now + (window_seconds / float(limit)) if limit else now,
            reason=None,
        )


class RateLimiter:
    def __init__(self) -> None:
        self._strategies = {
            'fixed_window': FixedWindowStrategy(),
            'sliding_window': SlidingWindowStrategy(),
            'token_bucket': TokenBucketStrategy(),
        }

    def check(self, key: str, limit: int, window_seconds: int, algorithm: AlgorithmName) -> RateLimitDecision:
        strategy = self._strategies.get(algorithm, self._strategies['sliding_window'])
        return strategy.allow(key, limit, window_seconds)
