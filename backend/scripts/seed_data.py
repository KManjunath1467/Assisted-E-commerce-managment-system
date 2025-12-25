"""
Seed script: populates all tables with 30 days of realistic mock data.

Usage (from backend/):
    python -m scripts.seed_data

Requires DATABASE_URL in .env or environment.
"""

import asyncio
import random
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# Ensure the backend directory is on the path when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from core.enums import ActionStatus, ActionType, CampaignStatus, IncidentStatus
from db.engine import get_engine
from db.models import Action, CampaignModel, Incident, Inventory, Product, Sale, Ticket

TODAY = date(2026, 4, 9)
YESTERDAY = TODAY - timedelta(days=1)  # April 8 — the dip day
START_DATE = TODAY - timedelta(days=30)

REGIONS = ["north", "south", "east", "west"]

# Product catalog — single source of truth for name, category, and pricing
PRODUCTS = [
    {
        "product_id": "PRD-001",
        "name": "Wireless Headphones",
        "category": "Electronics",
        "unit_price": 149.99,
    },
    {
        "product_id": "PRD-002",
        "name": "Running Shoes",
        "category": "Footwear",
        "unit_price": 119.99,
    },
    {
        "product_id": "PRD-003",
        "name": "Laptop Stand",
        "category": "Electronics",
        "unit_price": 44.99,
    },
    {
        "product_id": "PRD-004",
        "name": "USB-C Hub",
        "category": "Electronics",
        "unit_price": 34.99,
    },
    {
        "product_id": "PRD-005",
        "name": "Yoga Mat",
        "category": "Fitness",
        "unit_price": 54.99,
    },
]

# Stock levels seeded separately — inventory is stock-only
INVENTORY = [
    {"product_id": "PRD-001", "stock": 450},
    {"product_id": "PRD-002", "stock": 12},  # low stock
    {"product_id": "PRD-003", "stock": 0},  # out of stock
    {"product_id": "PRD-004", "stock": 200},
    {"product_id": "PRD-005", "stock": 28},  # low stock
]

# product_id -> unit_price lookup used by order builder
_PRICE = {p["product_id"]: p["unit_price"] for p in PRODUCTS}

CAMPAIGNS = [
    {
        "name": "Spring Sale",
        "channel": "email",
        "status": CampaignStatus.ACTIVE,
        "performance": {
            "impressions": 82000,
            "clicks": 3280,
            "conversions": 164,
            "spend": 1800.00,
            "roas": 3.2,
            "ctr": 0.04,
        },
    },
    {
        "name": "Weekend Social Boost",
        "channel": "social",
        "status": CampaignStatus.PAUSED,  # paused — contributes to the dip
        "performance": {
            "impressions": 45000,
            "clicks": 900,
            "conversions": 27,
            "spend": 1200.00,
            "roas": 1.1,
            "ctr": 0.02,
        },
    },
    {
        "name": "Search Brand Keywords",
        "channel": "search",
        "status": CampaignStatus.ACTIVE,
        "performance": {
            "impressions": 31000,
            "clicks": 1550,
            "conversions": 93,
            "spend": 2200.00,
            "roas": 2.8,
            "ctr": 0.05,
        },
    },
]


def _orders_for_day(product_id: str, day: date) -> list[dict]:
    """Return a list of order dicts for a given product and day."""
    price = _PRICE[product_id]

    # No sales for out-of-stock product from yesterday onwards
    if product_id == "PRD-003" and day >= YESTERDAY:
        return []

    # Severely reduced for low-stock product on the dip day
    if product_id == "PRD-002" and day == YESTERDAY:
        qty = 1
        return [
            {
                "id": uuid.uuid4(),
                "date": day,
                "product_id": product_id,
                "revenue": round(price * qty, 2),
                "quantity": qty,
                "region": random.choice(REGIONS),
            }
        ]

    # Dip day: ~40% volume across other products (campaign paused effect)
    if day == YESTERDAY:
        order_count = random.randint(1, 2)
    else:
        order_count = random.randint(2, 4)

    orders = []
    used_regions = random.sample(REGIONS, k=min(order_count, len(REGIONS)))
    for region in used_regions:
        qty = random.randint(1, 2)
        orders.append(
            {
                "id": uuid.uuid4(),
                "date": day,
                "product_id": product_id,
                "revenue": round(price * qty, 2),
                "quantity": qty,
                "region": region,
            }
        )
    return orders


def _build_ticket_rows() -> list[dict]:
    """Build 30 days of ticket rows matching the sales dip narrative."""
    rows = []
    delta = (TODAY - START_DATE).days

    # Category mix for normal days
    NORMAL_CATEGORIES = [
        ("shipping_delay", -0.3, False, False),
        ("product_quality", -0.2, False, False),
        ("billing_issue", -0.1, False, False),
        ("general_inquiry", 0.1, False, False),
        ("refund_request", -0.5, True, False),
        ("return_request", -0.4, False, True),
    ]

    for offset in range(delta):
        day = START_DATE + timedelta(days=offset)
        is_dip = day == YESTERDAY

        if is_dip:
            # Dip day: ~2x normal volume, dominated by out_of_stock and refund complaints
            ticket_count = random.randint(60, 80)
            dip_categories = [
                ("out_of_stock", -0.8, False, False),
                ("out_of_stock", -0.8, False, False),
                ("out_of_stock", -0.8, False, False),
                ("shipping_delay", -0.6, False, False),
                ("shipping_delay", -0.6, False, False),
                ("refund_request", -0.7, True, False),
                ("refund_request", -0.7, True, False),
                ("return_request", -0.6, False, True),
            ]
            weights = [3, 3, 3, 2, 2, 2, 2, 1]
        else:
            ticket_count = random.randint(30, 45)
            dip_categories = NORMAL_CATEGORIES
            weights = [3, 2, 1, 2, 1, 1]

        for _ in range(ticket_count):
            cat, sentiment, is_refund, is_return = random.choices(dip_categories, weights=weights)[0]
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "date": day,
                    "category": cat,
                    "sentiment_score": round(sentiment + random.uniform(-0.1, 0.1), 2),
                    "is_refund": is_refund,
                    "is_return": is_return,
                    "review_text": None,
                }
            )

    return rows


def _build_sales_rows() -> list[dict]:
    rows = []
    delta = (TODAY - START_DATE).days
    for offset in range(delta):
        day = START_DATE + timedelta(days=offset)
        for inv in INVENTORY:
            rows.extend(_orders_for_day(inv["product_id"], day))
    return rows


def _build_historical_incident() -> tuple[dict, list[dict]]:
    """One resolved incident from ~30 days ago with two executed actions."""
    incident_id = uuid.uuid4()
    created = datetime(2026, 3, 10, 9, 0, tzinfo=UTC)
    resolved = datetime(2026, 3, 12, 14, 0, tzinfo=UTC)

    incident = {
        "id": incident_id,
        "summary": (
            "Sales declined 28% over two days driven by Yoga Mat stockout. "
            "Weekend Social Boost campaign spend was exhausted simultaneously, "
            "reducing top-of-funnel traffic. Restocking and a 10% discount "
            "restored normal revenue within 48 hours."
        ),
        "signals": {
            "domains": ["inventory", "sales", "marketing"],
            "affected_products": ["PRD-005"],
            "revenue_drop_pct": -28.5,
            "stockout_detected": True,
            "campaign_issue": "budget_exhausted",
        },
        "status": IncidentStatus.RESOLVED,
        "created_at": created,
        "resolved_at": resolved,
    }

    actions = [
        {
            "id": uuid.uuid4(),
            "incident_id": incident_id,
            "action_type": ActionType.RESTOCK,
            "description": "Emergency restock of 500 units for Yoga Mat (PRD-005)",
            "status": ActionStatus.EXECUTED,
            "created_at": created + timedelta(hours=1),
            "executed_at": created + timedelta(hours=3),
        },
        {
            "id": uuid.uuid4(),
            "incident_id": incident_id,
            "action_type": ActionType.RUN_DISCOUNT,
            "description": "10% discount on Yoga Mat and Wireless Headphones for 48h",
            "status": ActionStatus.EXECUTED,
            "created_at": created + timedelta(hours=1),
            "executed_at": created + timedelta(hours=4),
        },
    ]
    return incident, actions


async def seed() -> None:
    engine = get_engine()
    sales_rows = _build_sales_rows()
    ticket_rows = _build_ticket_rows()

    async with engine.begin() as conn:
        # Clear existing data in dependency order
        await conn.execute(text("DELETE FROM actions"))
        await conn.execute(text("DELETE FROM sales"))
        await conn.execute(text("DELETE FROM campaigns"))
        await conn.execute(text("DELETE FROM inventory"))
        await conn.execute(text("DELETE FROM incidents"))
        await conn.execute(text("DELETE FROM tickets"))
        await conn.execute(text("DELETE FROM products"))

    async with engine.begin() as conn:
        # Products (catalog — must be seeded before inventory and sales)
        await conn.execute(
            Product.__table__.insert(),
            [
                {
                    "id": uuid.uuid4(),
                    **p,
                }
                for p in PRODUCTS
            ],
        )

        # Inventory (stock levels only — references products)
        await conn.execute(
            Inventory.__table__.insert(),
            [
                {
                    "id": uuid.uuid4(),
                    "updated_at": datetime.now(UTC),
                    **inv,
                }
                for inv in INVENTORY
            ],
        )

        # Campaigns
        await conn.execute(
            CampaignModel.__table__.insert(),
            [
                {
                    "id": uuid.uuid4(),
                    "updated_at": datetime.now(UTC),
                    **c,
                }
                for c in CAMPAIGNS
            ],
        )

        # Sales
        # Insert in chunks to avoid parameter limits
        chunk_size = 500
        for i in range(0, len(sales_rows), chunk_size):
            await conn.execute(Sale.__table__.insert(), sales_rows[i : i + chunk_size])

        # Historical incident + actions (for memory recall testing)
        incident, actions = _build_historical_incident()
        await conn.execute(Incident.__table__.insert(), [incident])
        await conn.execute(Action.__table__.insert(), actions)

        # Tickets
        chunk_size = 500
        for i in range(0, len(ticket_rows), chunk_size):
            await conn.execute(Ticket.__table__.insert(), ticket_rows[i : i + chunk_size])

    await engine.dispose()

    # Index the historical resolved incident into Qdrant for vector search.
    try:
        from db.qdrant_store import index_incident

        await index_incident(
            incident_id=str(incident["id"]),
            summary=incident["summary"],
            actions_taken=[a["action_type"] for a in actions],
            query="Sales declined driven by Yoga Mat stockout and paused campaign",
        )
        print("Indexed historical incident into Qdrant")
    except Exception as exc:
        print(f"Qdrant indexing skipped ({exc})")

    end_date = TODAY - timedelta(days=1)
    total_sales = len(sales_rows)
    print(f"Seeded {len(PRODUCTS)} products (with pricing)")
    print(f"Seeded {len(INVENTORY)} inventory records")
    print(f"Seeded {len(CAMPAIGNS)} campaigns")
    print(f"Seeded {total_sales} sales rows ({START_DATE} to {end_date})")
    print("Seeded 1 resolved incident with 2 executed actions")
    print(f"Seeded {len(ticket_rows)} ticket rows ({START_DATE} to {TODAY - timedelta(days=1)})")
    print(f"Dip day: {YESTERDAY} — reduced volume on all products, zero for PRD-003")


if __name__ == "__main__":
    asyncio.run(seed())
