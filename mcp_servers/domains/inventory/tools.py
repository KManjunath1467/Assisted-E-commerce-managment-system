"""Inventory domain MCP tools — business logic only, delegates SQL to repository."""

from datetime import date, timedelta

from .repository import InventoryRepository
from .schemas import InventoryAnalysis, ProductRef, StockLevel

REORDER_POINT = 30  # low-stock threshold (units)


def _parse_date(d: str) -> date:
    return date.fromisoformat(d)


async def get_inventory_snapshot(as_of_date: str = "") -> dict:
    """Get current inventory levels, classifying out-of-stock and low-stock products.

    Args:
        as_of_date: Optional ISO date (YYYY-MM-DD) for historical snapshot. Defaults to today when empty.
    """
    target = _parse_date(as_of_date) if as_of_date else date.today()
    repo = InventoryRepository()

    inv_rows = await repo.fetch_inventory()
    prod_rows = await repo.fetch_products()
    sale_rows = await repo.fetch_sales_by_date_range(target - timedelta(days=7), target)

    prod_map = {p["product_id"]: p for p in prod_rows}

    velocity: dict[str, float] = {}
    for r in sale_rows:
        velocity[r["product_id"]] = velocity.get(r["product_id"], 0.0) + r["quantity"]
    velocity = {pid: qty / 7.0 for pid, qty in velocity.items()}

    stock_levels = []
    for inv in inv_rows:
        prod = prod_map.get(inv["product_id"])
        ref = ProductRef(
            product_id=inv["product_id"],
            name=prod["name"] if prod else inv["product_id"],
        )
        daily_vel = velocity.get(inv["product_id"], 0.0)
        days_until = (
            (inv["stock"] / daily_vel) if daily_vel > 0 and inv["stock"] > 0 else None
        )
        sl = StockLevel(
            product=ref,
            quantity=inv["stock"],
            unit_price=float(prod["unit_price"]) if prod else None,
            reorder_point=REORDER_POINT,
            days_until_stockout=round(days_until, 1)
            if days_until is not None
            else None,
            is_out_of_stock=inv["stock"] == 0,
        )
        stock_levels.append(sl)

    out_of_stock = [sl.product for sl in stock_levels if sl.is_out_of_stock]
    low_stock = [
        sl
        for sl in stock_levels
        if not sl.is_out_of_stock and sl.quantity < REORDER_POINT
    ]

    insights = []
    if out_of_stock:
        insights.append(f"Out of stock: {', '.join(p.name for p in out_of_stock)}")
    if low_stock:
        low_names = ", ".join(s.product.name for s in low_stock)
        insights.append(f"Low stock (< {REORDER_POINT} units): {low_names}")

    result = InventoryAnalysis(
        kind="inventory",
        stock_levels=stock_levels,
        insights=insights,
    )
    return result.model_dump(mode="json")


async def get_stockout_impact(date_str: str) -> dict:
    """Identify out-of-stock products that had sales in the 7 days prior to date — lost sales signal.

    Args:
        date_str: Target date in YYYY-MM-DD format.
    """
    target = _parse_date(date_str)
    repo = InventoryRepository()

    inv_rows = await repo.fetch_inventory()
    prod_rows = await repo.fetch_products()
    prior_sales = await repo.fetch_sales_by_date_range(
        target - timedelta(days=7), target
    )

    prod_map = {p["product_id"]: p for p in prod_rows}
    name_map = {pid: p["name"] for pid, p in prod_map.items()}
    stockout_ids = {r["product_id"] for r in inv_rows if r["stock"] == 0}
    impacted = stockout_ids & {r["product_id"] for r in prior_sales}
    missed_views = [
        ProductRef(product_id=pid, name=name_map.get(pid, pid)) for pid in impacted
    ]

    lost_revenue = (
        sum(float(r["revenue"]) for r in prior_sales if r["product_id"] in impacted)
        / 7.0
    )

    stock_levels = [
        StockLevel(
            product=ProductRef(
                product_id=r["product_id"],
                name=name_map.get(r["product_id"], r["product_id"]),
            ),
            quantity=r["stock"],
            unit_price=float(prod_map[r["product_id"]]["unit_price"])
            if r["product_id"] in prod_map
            else None,
            reorder_point=REORDER_POINT,
            is_out_of_stock=r["stock"] == 0,
        )
        for r in inv_rows
    ]

    insights = []
    if missed_views:
        insights.append(
            f"Stockout impact on {', '.join(p.name for p in missed_views)} — est. ${lost_revenue:,.2f}/day lost revenue"
        )

    result = InventoryAnalysis(
        kind="inventory",
        stock_levels=stock_levels,
        stockout_missed_views=missed_views,
        estimated_sales_impact=round(lost_revenue, 2) if lost_revenue else None,
        insights=insights,
    )
    return result.model_dump(mode="json")
