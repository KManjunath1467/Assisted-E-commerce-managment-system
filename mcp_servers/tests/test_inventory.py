"""Tool-layer tests for inventory domain against a seeded database.

Run:  cd mcp_servers && uv run pytest tests/test_inventory.py -v
"""

from domains.inventory.tools import get_inventory_snapshot, get_stockout_impact

DIP_DAY = "2026-04-08"
REORDER_POINT = 30


async def test_inventory_snapshot_prd003_out_of_stock():
    result = await get_inventory_snapshot()
    oos_ids = [
        sl["product"]["product_id"]
        for sl in result["stock_levels"]
        if sl["is_out_of_stock"]
    ]
    assert "PRD-003" in oos_ids, f"Expected PRD-003 out-of-stock, got: {oos_ids}"


async def test_inventory_snapshot_low_stock():
    result = await get_inventory_snapshot()
    low_ids = [
        sl["product"]["product_id"]
        for sl in result["stock_levels"]
        if not sl["is_out_of_stock"] and sl["quantity"] < REORDER_POINT
    ]
    # PRD-002 (12 units) and PRD-005 (28 units) are below reorder point of 30
    assert "PRD-002" in low_ids or "PRD-005" in low_ids, (
        f"Expected low-stock products, got: {low_ids}"
    )


async def test_inventory_snapshot_returns_expected_keys():
    result = await get_inventory_snapshot()
    assert result["kind"] == "inventory"
    assert "stock_levels" in result
    assert "insights" in result
    if result["stock_levels"]:
        sl = result["stock_levels"][0]
        assert "product" in sl
        assert "quantity" in sl
        assert "is_out_of_stock" in sl


async def test_stockout_impact_flags_prd003():
    result = await get_stockout_impact(date_str=DIP_DAY)
    missed_ids = [p["product_id"] for p in result["stockout_missed_views"]]
    assert "PRD-003" in missed_ids, (
        f"Expected PRD-003 in stockout impact, got: {missed_ids}"
    )
