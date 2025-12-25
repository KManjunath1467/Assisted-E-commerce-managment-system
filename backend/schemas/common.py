"""Backend-only helpers for common types."""

from datetime import UTC, date, datetime, timedelta

from domains.common import TimeRange


def default_time_range() -> TimeRange:
    """Return a TimeRange covering yesterday 00:00–23:59 UTC."""
    yesterday = date.today() - timedelta(days=1)
    return TimeRange(
        start=datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0, tzinfo=UTC),
        end=datetime(
            yesterday.year,
            yesterday.month,
            yesterday.day,
            23,
            59,
            59,
            tzinfo=UTC,
        ),
    )
