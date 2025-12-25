"""Write tool tests — verify each execute_* MCP tool mutates the database correctly.

Each test seeds minimal fixture rows, calls the tool, asserts DB state changed,
then cleans up its own rows so the seeded dataset is not permanently modified.

Run:  cd mcp_servers && uv run pytest tests/test_actions.py -v
"""

import uuid

import pytest
from db import get_session_factory
from domains.customer_support.tools import execute_create_support_ticket
from domains.db_tables import campaigns as _campaigns
from domains.db_tables import inventory as _inventory
from domains.db_tables import products as _products
from domains.db_tables import tickets as _tickets
from domains.inventory.tools import execute_restock
from domains.marketing.tools import execute_pause_campaign, execute_resume_campaign
from domains.sales.tools import execute_run_discount
from sqlalchemy import delete, insert, select

pytestmark = pytest.mark.asyncio


# ── execute_restock ────────────────────────────────────────────────────────────


async def test_execute_restock_increases_stock():
    """execute_restock adds qty units to each listed product's stock."""
    pid = f"TEST-RESTOCK-{uuid.uuid4().hex[:8]}"
    factory = get_session_factory()

    async with factory() as session:
        await session.execute(insert(_inventory).values(product_id=pid, stock=10))
        await session.commit()

    try:
        result = await execute_restock(targets=[pid], qty=50)

        assert result["updated"] == 1
        assert "50" in result["message"]

        async with factory() as session:
            row = (await session.execute(select(_inventory).where(_inventory.c.product_id == pid))).one()
            assert row.stock == 60
    finally:
        async with factory() as session:
            await session.execute(delete(_inventory).where(_inventory.c.product_id == pid))
            await session.commit()


async def test_execute_restock_empty_targets():
    result = await execute_restock(targets=[])
    assert result["updated"] == 0


# ── execute_pause_campaign ─────────────────────────────────────────────────────


async def test_execute_pause_campaign_sets_paused():
    """execute_pause_campaign sets status to 'paused' for the given campaign UUIDs."""
    cid = str(uuid.uuid4())
    factory = get_session_factory()

    async with factory() as session:
        await session.execute(
            insert(_campaigns).values(
                id=cid,
                name="Test Campaign",
                channel="email",
                status="active",
                performance={},
            )
        )
        await session.commit()

    try:
        result = await execute_pause_campaign(targets=[cid])

        assert result["updated"] == 1
        assert "1" in result["message"]

        async with factory() as session:
            row = (await session.execute(select(_campaigns).where(_campaigns.c.id == cid))).one()
            assert row.status == "paused"
    finally:
        async with factory() as session:
            await session.execute(delete(_campaigns).where(_campaigns.c.id == cid))
            await session.commit()


async def test_execute_pause_campaign_empty_targets():
    result = await execute_pause_campaign(targets=[])
    assert result["updated"] == 0


# ── execute_resume_campaign ────────────────────────────────────────────────────


async def test_execute_resume_campaign_sets_active():
    """execute_resume_campaign sets status to 'active' for the given campaign UUIDs."""
    cid = str(uuid.uuid4())
    factory = get_session_factory()

    async with factory() as session:
        await session.execute(
            insert(_campaigns).values(
                id=cid,
                name="Test Paused Campaign",
                channel="social",
                status="paused",
                performance={},
            )
        )
        await session.commit()

    try:
        result = await execute_resume_campaign(targets=[cid])

        assert result["updated"] == 1
        assert "1" in result["message"]

        async with factory() as session:
            row = (await session.execute(select(_campaigns).where(_campaigns.c.id == cid))).one()
            assert row.status == "active"
    finally:
        async with factory() as session:
            await session.execute(delete(_campaigns).where(_campaigns.c.id == cid))
            await session.commit()


async def test_execute_resume_campaign_empty_targets():
    result = await execute_resume_campaign(targets=[])
    assert result["updated"] == 0


# ── execute_run_discount ───────────────────────────────────────────────────────


async def test_execute_run_discount_activates_discount():
    """execute_run_discount sets discount_pct and discount_active=True on the product."""
    pid = f"TEST-DISC-{uuid.uuid4().hex[:8]}"
    factory = get_session_factory()

    async with factory() as session:
        await session.execute(
            insert(_products).values(
                product_id=pid,
                name="Test Discount Product",
                category="test",
                unit_price=100,
                discount_pct=None,
                discount_active=False,
            )
        )
        await session.commit()

    try:
        result = await execute_run_discount(targets=[pid], discount_pct=20)

        assert result["updated"] == 1
        assert "20" in result["message"]

        async with factory() as session:
            row = (await session.execute(select(_products).where(_products.c.product_id == pid))).one()
            assert int(row.discount_pct) == 20
            assert row.discount_active is True
    finally:
        async with factory() as session:
            await session.execute(delete(_products).where(_products.c.product_id == pid))
            await session.commit()


async def test_execute_run_discount_empty_targets():
    result = await execute_run_discount(targets=[])
    assert result["updated"] == 0


# ── execute_create_support_ticket ──────────────────────────────────────────────


async def test_execute_create_support_ticket_inserts_row():
    """execute_create_support_ticket inserts an escalation ticket and returns its ID."""
    description = f"Test escalation ticket {uuid.uuid4().hex[:8]}"

    result = await execute_create_support_ticket(description=description)

    assert "ticket_id" in result
    assert result["message"] == "Support ticket created."

    ticket_id = result["ticket_id"]
    factory = get_session_factory()

    try:
        async with factory() as session:
            row = (await session.execute(select(_tickets).where(_tickets.c.id == ticket_id))).one()
            assert row.category == "escalation"
            assert row.review_text == description
            assert row.is_refund is False
            assert row.is_return is False
    finally:
        async with factory() as session:
            await session.execute(delete(_tickets).where(_tickets.c.id == ticket_id))
            await session.commit()
