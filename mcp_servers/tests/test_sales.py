"""Tool-layer tests for sales domain against a seeded database.

Run:  cd mcp_servers && uv run pytest tests/test_sales.py -v
"""

from domains.sales.tools import (
    compare_sales_periods,
    detect_revenue_anomalies,
    get_daily_sales_metrics,
)

DIP_DAY = "2026-04-08"
NORMAL_DAY = "2026-04-07"


async def test_daily_sales_dip_day_lower_than_normal():
    dip = await get_daily_sales_metrics(start_date=DIP_DAY)
    normal = await get_daily_sales_metrics(start_date=NORMAL_DAY)
    assert dip["metrics"]["total_revenue"] < normal["metrics"]["total_revenue"], (
        f"Dip day revenue ${dip['metrics']['total_revenue']:.2f} should be less than "
        f"normal day ${normal['metrics']['total_revenue']:.2f}"
    )


async def test_daily_sales_returns_expected_keys():
    result = await get_daily_sales_metrics(start_date=DIP_DAY)
    assert result["kind"] == "sales"
    assert "metrics" in result
    assert "insights" in result
    m = result["metrics"]
    assert "total_revenue" in m
    assert "order_count" in m
    assert "avg_order_value" in m
    assert "top_products" in m
    assert "by_region" in m


async def test_compare_sales_periods_shows_decline():
    result = await compare_sales_periods(current_date=DIP_DAY, days_back=7)
    assert result["comparison_period"] is not None
    assert (
        result["metrics"]["total_revenue"]
        < result["comparison_period"]["total_revenue"]
    ), "Dip day should show lower revenue than 7-day daily average"


async def test_detect_revenue_anomalies_on_dip_day():
    anomalies = await detect_revenue_anomalies(current_date=DIP_DAY)
    assert len(anomalies) > 0, "Expected revenue anomaly on dip day"
    assert any(a["deviation_pct"] < -20 for a in anomalies), (
        "Expected >20% revenue drop anomaly"
    )


async def test_detect_revenue_anomalies_normal_day():
    anomalies = await detect_revenue_anomalies(current_date=NORMAL_DAY)
    assert isinstance(anomalies, list)
