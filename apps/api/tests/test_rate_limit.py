"""Tests for sliding-window customer rate limiter."""

from app.services.pipeline.rate_limit import CustomerRateLimiter


def test_rate_limiter_allows_up_to_max():
    """Verify customer can send up to max_requests within window."""
    limiter = CustomerRateLimiter(max_requests=3, window_seconds=60.0)
    phone = "+919999911111"

    assert limiter.is_allowed(phone) is True
    assert limiter.is_allowed(phone) is True
    assert limiter.is_allowed(phone) is True
    # 4th request exceeds limit
    assert limiter.is_allowed(phone) is False


def test_rate_limiter_isolates_by_phone():
    """Verify limits on phone A do not restrict phone B."""
    limiter = CustomerRateLimiter(max_requests=2, window_seconds=60.0)
    phone_a = "1111"
    phone_b = "2222"

    assert limiter.is_allowed(phone_a) is True
    assert limiter.is_allowed(phone_a) is True
    assert limiter.is_allowed(phone_a) is False

    # phone_b is still allowed
    assert limiter.is_allowed(phone_b) is True
    assert limiter.is_allowed(phone_b) is True


def test_rate_limiter_reset():
    """Verify reset clears rate history."""
    limiter = CustomerRateLimiter(max_requests=1, window_seconds=60.0)
    phone = "3333"

    assert limiter.is_allowed(phone) is True
    assert limiter.is_allowed(phone) is False

    limiter.reset(phone)
    assert limiter.is_allowed(phone) is True
