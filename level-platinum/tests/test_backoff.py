"""Tests for backoff.retry_with_backoff decorator."""

import asyncio
import pytest

from backoff import retry_with_backoff


# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


def test_sync_succeeds_on_first_try():
    calls = []

    @retry_with_backoff(max_tries=3, base_delay=0.01)
    def fn():
        calls.append(1)
        return "ok"

    assert fn() == "ok"
    assert len(calls) == 1


def test_sync_retries_and_eventually_succeeds():
    calls = []

    @retry_with_backoff(max_tries=5, base_delay=0.01)
    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("not yet")
        return "done"

    result = fn()
    assert result == "done"
    assert len(calls) == 3


def test_sync_raises_after_all_retries_exhausted():
    @retry_with_backoff(max_tries=3, base_delay=0.01)
    def fn():
        raise RuntimeError("always fails")

    with pytest.raises(RuntimeError, match="always fails"):
        fn()


def test_sync_preserves_function_name_and_doc():
    @retry_with_backoff(max_tries=3, base_delay=0.01)
    def my_special_fn():
        """My docstring."""
        return 42

    assert my_special_fn.__name__ == "my_special_fn"
    assert "docstring" in my_special_fn.__doc__


def test_sync_passes_args_and_kwargs():
    @retry_with_backoff(max_tries=3, base_delay=0.01)
    def add(a, b, *, c=0):
        return a + b + c

    assert add(1, 2, c=3) == 6


def test_sync_returns_correct_attempt_count_on_retry():
    """Ensure exactly max_tries calls are made when always failing."""
    calls = []

    @retry_with_backoff(max_tries=4, base_delay=0.001)
    def fn():
        calls.append(1)
        raise OSError("fail")

    with pytest.raises(OSError):
        fn()

    assert len(calls) == 4


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


def test_async_succeeds_on_first_try():
    @retry_with_backoff(max_tries=3, base_delay=0.01)
    async def async_fn():
        return "async_ok"

    result = asyncio.run(async_fn())
    assert result == "async_ok"


def test_async_retries_and_eventually_succeeds():
    calls = []

    @retry_with_backoff(max_tries=5, base_delay=0.01)
    async def async_fn():
        calls.append(1)
        if len(calls) < 2:
            raise ConnectionError("not connected")
        return "connected"

    result = asyncio.run(async_fn())
    assert result == "connected"
    assert len(calls) == 2


def test_async_raises_after_all_retries_exhausted():
    @retry_with_backoff(max_tries=3, base_delay=0.01)
    async def async_fn():
        raise TimeoutError("timed out")

    with pytest.raises(TimeoutError, match="timed out"):
        asyncio.run(async_fn())


def test_async_preserves_function_name():
    @retry_with_backoff(max_tries=3, base_delay=0.01)
    async def my_async_fn():
        return 99

    assert my_async_fn.__name__ == "my_async_fn"


def test_async_passes_args_and_kwargs():
    @retry_with_backoff(max_tries=3, base_delay=0.01)
    async def multiply(x, *, factor=2):
        return x * factor

    assert asyncio.run(multiply(5, factor=3)) == 15


# ---------------------------------------------------------------------------
# Logging integration (no logs_path → stderr fallback)
# ---------------------------------------------------------------------------


def test_sync_logs_to_stderr_when_no_logs_path(capsys):
    @retry_with_backoff(max_tries=2, base_delay=0.01)
    def fn():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        fn()

    captured = capsys.readouterr()
    assert "backoff WARNING" in captured.err
    assert "backoff CRITICAL" in captured.err
