from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, List


def _exponential(base: float, cap: float) -> Callable[[int], float]:
    def f(attempt: int) -> float:
        raw = base * (2.0 ** max(0, attempt))
        return min(raw, cap)
    return f


@dataclass(frozen=True)
class BackoffResult:
    delays: List[float]
    success: bool


class BackoffPlan:
    def __init__(
        self,
        *,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        deadline: float = 120.0,
        max_attempts: int = 10,
        jitter=None,
        clock: Callable[[], float] = time.monotonic,
        rand: Callable[[], float] = None,
    ):
        if base_delay <= 0:
            raise ValueError("base_delay must be positive")
        if max_delay <= 0:
            raise ValueError("max_delay must be positive")
        if deadline < 0:
            raise ValueError("deadline must be non-negative")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if jitter not in (None, "full"):
            raise ValueError("jitter must be None or 'full'")

        self._base_delay = base_delay
        self._max_delay = max_delay
        self._deadline = deadline
        self._max_attempts = max_attempts
        self._jitter = jitter
        self._clock = clock
        self._rand = rand if rand is not None else (lambda: 0.5)
        self._compute_delay = _exponential(base_delay, max_delay)

    def run(self, should_retry: Callable[[int, Exception], bool]) -> BackoffResult:
        start = self._clock()
        elapsed_scheduled = 0.0
        delays: List[float] = []
        attempt = 0
        success = False

        while attempt < self._max_attempts:
            if self._clock() - start + elapsed_scheduled >= self._deadline:
                break

            try:
                should_retry(attempt, None)
                success = True
                break
            except Exception as exc:
                if not isinstance(exc, Exception):
                    raise

                remaining = self._deadline - (self._clock() - start + elapsed_scheduled)
                if remaining <= 0:
                    break

                if attempt + 1 >= self._max_attempts:
                    break

                if not self._allow_retry(attempt, exc):
                    break

                delay = self._compute_delay(attempt)
                if self._jitter == "full":
                    delay = delay * self._rand()

                delay = min(delay, remaining)
                delays.append(delay)
                elapsed_scheduled += delay
                attempt += 1

        return BackoffResult(delays=delays, success=success)

    def _allow_retry(self, attempt: int, exc: Exception) -> bool:
        return True
