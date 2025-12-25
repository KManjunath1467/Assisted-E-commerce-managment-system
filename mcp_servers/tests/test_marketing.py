"""Tool-layer tests for marketing domain against a seeded database.

Run:  cd mcp_servers && uv run pytest tests/test_marketing.py -v
"""

from domains.marketing.tools import get_campaign_status


async def test_campaign_weekend_social_underperforming():
    result = await get_campaign_status()
    underperforming_names = [c["name"] for c in result["underperforming"]]
    assert "Weekend Social Boost" in underperforming_names, (
        f"Expected 'Weekend Social Boost' as underperforming, got: {underperforming_names}"
    )


async def test_campaign_worst_channel_is_social():
    result = await get_campaign_status()
    assert result["worst_channel"] is not None
    assert result["worst_channel"] == "social", (
        f"Expected social, got {result['worst_channel']}"
    )


async def test_campaign_returns_expected_keys():
    result = await get_campaign_status()
    assert result["kind"] == "marketing"
    assert "campaigns" in result
    assert "underperforming" in result
    assert "worst_channel" in result
    assert "insights" in result
    if result["campaigns"]:
        c = result["campaigns"][0]
        assert "campaign_id" in c
        assert "name" in c
        assert "channel" in c
        assert "current_period" in c
