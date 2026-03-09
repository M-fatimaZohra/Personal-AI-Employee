"""Exponential backoff retry decorator + CircuitBreaker — sync and async.

Formula: delay = base_delay × 2^(attempt - 1) + jitter
         where jitter = random.uniform(0, base_delay)

Usage:
    from backoff import retry_with_backoff, CircuitBreaker

    @retry_with_backoff(max_tries=5, base_delay=1.0)
    def call_gmail_api():
        ...

    # Circuit breaker (protects long-running integrations like Odoo/social media)
    odoo_cb = CircuitBreaker(name="odoo", failure_threshold=3, timeout_seconds=900)
    result = odoo_cb.call(fetch_odoo_invoices)
"""

import asyncio
import functools
import random
import time
from pathlib import Path
from typing import Any, Callable


class ServiceDegradedError(Exception):
    """Raised when a circuit breaker is open and the service is unavailable."""


class CircuitBreaker:
    """State machine: closed → open (after N failures) → half_open (after timeout) → closed.

    States:
        closed:    Normal operation. Failures increment counter.
        open:      Service skipped. Raises ServiceDegradedError immediately.
        half_open: One probe attempt allowed. Success → closed; failure → open.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        timeout_seconds: float = 900.0,
        logs_path: Path | None = None,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.logs_path = logs_path

        self.state: str = "closed"
        self.failure_count: int = 0
        self.last_failure_time: float | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Call *func* respecting the current circuit state."""
        self._maybe_transition_to_half_open()

        if self.state == "open":
            retry_in = self._retry_in_seconds()
            raise ServiceDegradedError(
                f"Circuit breaker [{self.name}] is OPEN. "
                f"Retry in {retry_in:.0f}s."
            )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except ServiceDegradedError:
            raise
        except Exception as exc:
            self._on_failure(exc)
            raise

    @property
    def status(self) -> dict:
        """Return a status dict suitable for Dashboard display."""
        retry_in = self._retry_in_seconds() if self.state == "open" else None
        return {
            "service": self.name,
            "circuit_state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "retry_in_seconds": retry_in,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _maybe_transition_to_half_open(self) -> None:
        if self.state == "open" and self.last_failure_time is not None:
            if time.time() - self.last_failure_time >= self.timeout_seconds:
                self.state = "half_open"
                self._log("circuit_half_open", f"Probing {self.name} after timeout")

    def _on_success(self) -> None:
        if self.state in ("half_open", "open"):
            self._log("circuit_closed", f"{self.name} recovered — circuit closed")
        self.state = "closed"
        self.failure_count = 0
        self.last_failure_time = None

    def _on_failure(self, exc: Exception) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold or self.state == "half_open":
            self.state = "open"
            self._log(
                "circuit_opened",
                f"{self.name} circuit OPENED after {self.failure_count} failure(s): {exc}",
            )

    def _retry_in_seconds(self) -> float:
        if self.last_failure_time is None:
            return 0.0
        elapsed = time.time() - self.last_failure_time
        return max(0.0, self.timeout_seconds - elapsed)

    def _log(self, action: str, details: str) -> None:
        if self.logs_path is not None:
            from logger import log_action  # local import avoids circular deps

            log_action(self.logs_path, action, f"circuit_breaker:{self.name}", details=details)
        else:
            import sys

            print(f"[CircuitBreaker] {details}", file=sys.stderr)


def retry_with_backoff(
    max_tries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 300.0,
    logs_path: Path | None = None,
) -> Callable:
    """Decorator: retry a function with exponential backoff.

    Args:
        max_tries:   Total number of attempts (including the first). Default 5.
        base_delay:  Base delay in seconds before the first retry. Default 1.0.
        max_delay:   Upper bound on computed delay (seconds). Default 300.0.
        logs_path:   Optional path to vault ``Logs/`` directory.  When supplied,
                     retry warnings are written via ``logger.log_action``; when
                     ``None``, warnings are printed to stderr.

    Returns:
        A decorator that wraps synchronous or asynchronous callables.

    Raises:
        The last exception raised by the wrapped function after all retries are
        exhausted.  A critical log entry is written before re-raising.
    """

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)
        actor = f"backoff:{func.__name__}"

        # ----------------------------------------------------------------
        # Logging helpers — use logger.py when logs_path available, else stderr
        # ----------------------------------------------------------------

        def _warn(attempt: int, delay: float, exc: Exception) -> None:
            msg = (
                f"Attempt {attempt}/{max_tries} failed ({type(exc).__name__}: {exc}). "
                f"Retrying in {delay:.2f}s."
            )
            if logs_path is not None:
                from logger import log_action  # local import avoids circular deps

                log_action(
                    logs_path,
                    "retry_attempt",
                    actor,
                    result="error",
                    details=msg,
                )
            else:
                import sys

                print(f"[backoff WARNING] {msg}", file=sys.stderr)

        def _critical(exc: Exception) -> None:
            msg = (
                f"All {max_tries} attempt(s) exhausted for {func.__name__}. "
                f"Last error: {type(exc).__name__}: {exc}"
            )
            if logs_path is not None:
                from logger import log_action

                log_action(
                    logs_path,
                    "retry_exhausted",
                    actor,
                    result="error",
                    details=msg,
                )
            else:
                import sys

                print(f"[backoff CRITICAL] {msg}", file=sys.stderr)

        # ----------------------------------------------------------------
        # Delay formula
        # ----------------------------------------------------------------

        def _delay(attempt: int) -> float:
            """delay = base_delay × 2^(attempt-1) + jitter."""
            jitter = random.uniform(0, base_delay)
            raw = base_delay * (2 ** (attempt - 1)) + jitter
            return min(raw, max_delay)

        # ----------------------------------------------------------------
        # Async wrapper
        # ----------------------------------------------------------------

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: Exception = RuntimeError("No attempts made")
                for attempt in range(1, max_tries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as exc:
                        last_exc = exc
                        if attempt == max_tries:
                            break
                        delay = _delay(attempt)
                        _warn(attempt, delay, exc)
                        await asyncio.sleep(delay)
                _critical(last_exc)
                raise last_exc

            return async_wrapper

        # ----------------------------------------------------------------
        # Sync wrapper
        # ----------------------------------------------------------------

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception = RuntimeError("No attempts made")
            for attempt in range(1, max_tries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt == max_tries:
                        break
                    delay = _delay(attempt)
                    _warn(attempt, delay, exc)
                    time.sleep(delay)
            _critical(last_exc)
            raise last_exc

        return sync_wrapper

    return decorator
