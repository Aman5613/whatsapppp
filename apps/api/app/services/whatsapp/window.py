"""24-hour WhatsApp customer service window utility."""

from datetime import UTC, datetime, timedelta

_WINDOW_DURATION = timedelta(hours=24)


def is_within_service_window(last_customer_message_at: datetime | None) -> bool:
    """Return True if the customer sent a message within the last 24 hours.

    Meta WhatsApp Cloud API allows free-form session messages only within 24 hours
    of the customer's last message. Outside this window, session messages are rejected.
    """
    if last_customer_message_at is None:
        return False

    # Ensure timezone awareness (UTC)
    if last_customer_message_at.tzinfo is None:
        last_customer_message_at = last_customer_message_at.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    return (now - last_customer_message_at) <= _WINDOW_DURATION
