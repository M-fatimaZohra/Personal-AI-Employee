"""Exponential backoff retry decorator — works with both sync and async functions.

Formula: delay = base_delay × 2^(attempt - 1) + jitter
         where jitter = random.uniform(0, base_delay)

Usage:
    from backoff import retry_with_backoff

    @retry_with_backoff(max_tries=5, base_delay=1.0)
    def call_gmail_api():
        ...

    @retry_with_backoff(max_tries=3, base_delay=2.0, logs_path=self.logs)
    async def call_telegram_api():
        ...
"""

import asyncio
import functools
import random
import time
from pathlib import Path
from typing import Any, Callable


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
