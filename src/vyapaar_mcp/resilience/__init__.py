"""Circuit Breaker pattern for external API resilience.

Prevents cascading failures when external services (Razorpay, Google
Safe Browsing, Slack) are down or experiencing high latency.

States:
  CLOSED   — Normal operation. Failures are counted.
  OPEN     — Circuit is tripped. All calls fail immediately.
  HALF_OPEN — Trial period. One call is allowed through to test recovery.

Per CODE_REVIEW §5.3: "Circuit breaker pattern to prevent cascading failures."
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from enum import StrEnum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is OPEN."""

    def __init__(self, name: str, retry_after: float) -> None:
        self.name = name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit '{name}' is OPEN — retry after {retry_after:.1f}s"
        )


class CircuitBreaker:
    """Async circuit breaker for external service calls.

    Usage:
        cb = CircuitBreaker("razorpay", failure_threshold=5, recovery_timeout=30)

        try:
            result = await cb.call(some_async_function, arg1, arg2)
        except CircuitOpenError:
            # Service is down, use fallback
            ...
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            name: Human-readable name for logging.
            failure_threshold: Consecutive failures before OPEN.
            recovery_timeout: Seconds to wait before HALF_OPEN.
            half_open_max_calls: Max concurrent calls in HALF_OPEN state.
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls: int = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may auto-transition to HALF_OPEN)."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def failure_count(self) -> int:
        """Number of consecutive failures."""
        return self._failure_count

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute a function through the circuit breaker.

        Args:
            func: Async function to call.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            The result of the function call.

        Raises:
            CircuitOpenError: If the circuit is OPEN.
            Exception: Any exception from the wrapped function.
        """
        async with self._lock:
            current_state = self.state

            if current_state == CircuitState.OPEN:
                retry_after = self._recovery_timeout - (
                    time.monotonic() - self._last_failure_time
                )
                raise CircuitOpenError(self._name, max(0, retry_after))

            if (
                current_state == CircuitState.HALF_OPEN
                and self._half_open_calls >= self._half_open_max_calls
            ):
                raise CircuitOpenError(self._name, self._recovery_timeout)

            if current_state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1

        # Execute the function outside the lock
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure(e)
            raise

    async def _on_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            prev_state = self._state
            self._failure_count = 0
            self._success_count += 1
            self._half_open_calls = 0

            if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                self._state = CircuitState.CLOSED
                logger.info(
                    "Circuit '%s' CLOSED (recovered from %s)",
                    self._name,
                    prev_state,
                )

    async def _on_failure(self, error: Exception) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            self._success_count = 0

            if self._failure_count >= self._failure_threshold:
                prev_state = self._state
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning(
                    "Circuit '%s' OPEN after %d failures "
                    "(recovery in %.0fs) — last error: %s",
                    self._name,
                    self._failure_count,
                    self._recovery_timeout,
                    error,
                )

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        logger.info("Circuit '%s' manually RESET to CLOSED", self._name)

    def snapshot(self) -> dict[str, Any]:
        """Return circuit breaker status as a dict."""
        return {
            "name": self._name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self._failure_threshold,
            "recovery_timeout_s": self._recovery_timeout,
        }
