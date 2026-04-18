"""Tool-layer tests for customer support domain against a seeded database.

Run:  cd mcp_servers && uv run pytest tests/test_customer_support.py -v
"""

from datetime import date, timedelta

from domains.customer_support.tools import get_customer_support_snapshot

DIP_DAY = (date.today() - timedelta(days=1)).isoformat()
NORMAL_DAY = (date.today() - timedelta(days=2)).isoformat()


async def test_cx_dip_day_elevated_tickets():
    result = await get_customer_support_snapshot(date_str=DIP_DAY)
    assert result["period_tickets"] > 50, (
        f"Expected elevated tickets on dip day, got {result['period_tickets']}"
    )
    assert result["refund_rate"] > 0.1, (
        f"Expected elevated refund rate, got {result['refund_rate']}"
    )


async def test_cx_normal_day_baseline():
    result = await get_customer_support_snapshot(date_str=NORMAL_DAY)
    assert result["period_tickets"] < 50
    assert result["refund_rate"] < 0.15


async def test_cx_returns_expected_keys():
    result = await get_customer_support_snapshot(date_str=DIP_DAY)
    assert result["kind"] == "customer_support"
    assert "period_tickets" in result
    assert "previous_period_tickets" in result
    assert "tickets_change_pct" in result
    assert "refund_rate" in result
    assert "return_rate" in result
    assert "negative_reviews" in result
    assert "common_issues" in result
    assert "insights" in result
