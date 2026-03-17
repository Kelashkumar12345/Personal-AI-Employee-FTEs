"""Tests for the retry handler with exponential backoff."""

import pytest

from src.retry_handler import TransientError, with_retry


def test_success_on_first_attempt():
    call_count = 0

    @with_retry(max_attempts=3)
    def always_succeeds():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = always_succeeds()
    assert result == "ok"
    assert call_count == 1


def test_retries_on_transient_error(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    call_count = 0

    @with_retry(max_attempts=3, base_delay=0.01)
    def fails_twice():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise TransientError("temporary")
        return "recovered"

    result = fails_twice()
    assert result == "recovered"
    assert call_count == 3


def test_raises_after_max_attempts(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    @with_retry(max_attempts=3, base_delay=0.01)
    def always_fails():
        raise TransientError("always broken")

    with pytest.raises(TransientError):
        always_fails()


def test_non_transient_error_not_retried():
    call_count = 0

    @with_retry(max_attempts=3)
    def raises_value_error():
        nonlocal call_count
        call_count += 1
        raise ValueError("not transient")

    with pytest.raises(ValueError):
        raises_value_error()
    assert call_count == 1


def test_exponential_backoff_capped(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    @with_retry(max_attempts=4, base_delay=1.0, max_delay=3.0)
    def always_fails():
        raise TransientError("fail")

    with pytest.raises(TransientError):
        always_fails()

    assert sleep_calls[0] == 1.0   # 1 * 2^0
    assert sleep_calls[1] == 2.0   # 1 * 2^1
    assert sleep_calls[2] == 3.0   # capped at max_delay
