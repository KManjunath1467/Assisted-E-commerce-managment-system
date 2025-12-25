"""Shared pytest fixtures and DeepEval configuration."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# Ensure backend/ is on sys.path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _clear_agent_cache():
    """Clear the cached agents between tests so tool resolution is fresh."""
    from agents.nodes import clear_agent_cache

    clear_agent_cache()
    yield
    clear_agent_cache()


# ---------------------------------------------------------------------------
# Deterministic DB seed — runs once per session before any tests
# ---------------------------------------------------------------------------

_db_seeded = False
_db_seed_error: str | None = None


@pytest.fixture(scope="session", autouse=True)
def seed_database():
    """Seed the database once per test session so tool/graph tests are deterministic.

    If the DB is unreachable this stores the error message but does NOT skip —
    pure-schema tests (test_contracts) that never touch the DB can still run.
    Tests that need seeded data should use the ``require_db`` fixture.
    """
    global _db_seeded, _db_seed_error
    if not _db_seeded:
        try:
            from scripts.seed_data import seed

            asyncio.run(seed())
            _db_seeded = True
        except Exception as exc:
            _db_seed_error = str(exc)


@pytest.fixture
def require_db():
    """Skip the current test if DB seeding failed."""
    if not _db_seeded:
        pytest.skip(f"DB seed failed ({_db_seed_error}); skipping test that needs seeded data.")


@pytest.fixture
def require_qdrant():
    """Skip the current test if Qdrant is unreachable."""
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url="http://localhost:6333", timeout=3)
        client.get_collections()
        client.close()
    except Exception as exc:
        pytest.skip(f"Qdrant unavailable ({exc}); skipping test that needs Qdrant.")


# ---------------------------------------------------------------------------
# MCP registry — initialise once per session for integration tests
# ---------------------------------------------------------------------------

_mcp_initialized = False
_mcp_init_error: str | None = None


@pytest.fixture(scope="session", autouse=True)
def _init_mcp_registry():
    """Try to connect to MCP servers once per session.

    Integration tests that need tools (test_graph) use ``require_mcp`` to skip
    if MCP is unavailable. Contract/schema tests never call tools so they run
    regardless.
    """
    global _mcp_initialized, _mcp_init_error
    try:
        from agents.mcp_registry import initialize_mcp_registry

        asyncio.run(initialize_mcp_registry())
        _mcp_initialized = True
    except Exception as exc:
        _mcp_init_error = str(exc)


@pytest.fixture(scope="session", autouse=True)
def _mock_pg_store_if_db_unavailable(seed_database):
    """If the DB is unreachable (seed failed), patch save_incident and
    persist_hitl_incident_and_actions so graph/eval tests can run end-to-end
    without failing at the persistence step.

    Also always patches index_incident (Qdrant) since Qdrant ports are not
    published to the host and the in-graph Qdrant call should be a no-op in tests.
    """
    import unittest.mock as mock

    patches: list = []

    if not _db_seeded:
        patches.append(mock.patch("agents.nodes.save_incident", new=mock.AsyncMock(return_value="test-incident-uuid")))
        patches.append(
            mock.patch(
                "agents.nodes.persist_hitl_incident_and_actions",
                new=mock.AsyncMock(return_value=("test-incident-uuid", [])),
            )
        )

    for p in patches:
        p.start()

    yield

    for p in patches:
        p.stop()


@pytest.fixture(scope="session", autouse=True)
def _mock_mcp_if_empty(_init_mcp_registry):
    """If MCP registry loaded no tools (MCP servers not port-published to the host),
    inject mock StructuredTool objects backed by seeded-data-realistic responses
    so graph/eval tests can run end-to-end without live MCP server access.
    """
    import agents.mcp_registry as reg_module

    registry = reg_module._registry
    if registry is None or registry._tools:
        # Either MCP is disabled or real tools loaded successfully.
        return

    from datetime import UTC, date, datetime

    from domains.common import Anomaly, ProductRef, TimeRange
    from domains.customer_support.schemas import CustomerComplaint, CustomerSupportAnalysis
    from domains.inventory.schemas import InventoryAnalysis, StockLevel
    from domains.marketing.schemas import Campaign, CampaignMetrics, MarketingAnalysis
    from domains.sales.schemas import ProductRevenue, SalesAnalysis, SalesMetrics
    from langchain_core.tools import StructuredTool

    from core.enums import CampaignStatus, Channel, Severity

    _DIP_RANGE = TimeRange(
        start=datetime(2026, 4, 8, 0, 0, 0, tzinfo=UTC),
        end=datetime(2026, 4, 8, 23, 59, 59, tzinfo=UTC),
    )
    _NORMAL_METRICS = SalesMetrics(
        total_revenue=3200.0,
        order_count=22,
        avg_order_value=145.45,
        top_products=[
            ProductRevenue(product=ProductRef(product_id="PRD-001", name="Wireless Headphones"), revenue=1350.0),
            ProductRevenue(product=ProductRef(product_id="PRD-003", name="Laptop Stand"), revenue=900.0),
            ProductRevenue(product=ProductRef(product_id="PRD-002", name="Running Shoes"), revenue=600.0),
        ],
        by_region={"north": 900.0, "south": 800.0, "east": 750.0, "west": 750.0},
    )
    _DIP_METRICS = SalesMetrics(
        total_revenue=1280.0,
        order_count=9,
        avg_order_value=142.22,
        top_products=[
            ProductRevenue(product=ProductRef(product_id="PRD-001", name="Wireless Headphones"), revenue=750.0),
            ProductRevenue(product=ProductRef(product_id="PRD-002", name="Running Shoes"), revenue=120.0),
            ProductRevenue(product=ProductRef(product_id="PRD-004", name="USB-C Hub"), revenue=280.0),
        ],
        by_region={"north": 400.0, "south": 380.0, "east": 300.0, "west": 200.0},
    )

    async def get_daily_sales_metrics(date_str: str = ""):
        return SalesAnalysis(
            kind="sales",
            period=_DIP_RANGE,
            metrics=_DIP_METRICS,
            anomalies=[
                Anomaly(
                    metric="total_revenue", expected=3200.0, actual=1280.0, deviation_pct=-60.0, severity=Severity.HIGH
                ),
                Anomaly(metric="order_count", expected=22.0, actual=9.0, deviation_pct=-59.1, severity=Severity.HIGH),
            ],
            insights=[
                "Revenue of $1,280 is 60% below the 7-day average of $3,200.",
                "PRD-003 (Laptop Stand) generated $0 revenue — out of stock since April 8.",
                "Order count dropped from an average of 22 to 9 on the dip day.",
            ],
            comparison_period=_NORMAL_METRICS,
        )

    async def compare_sales_periods(start_date: str = "", end_date: str = "", compare_days: int = 7):
        return SalesAnalysis(
            kind="sales",
            period=_DIP_RANGE,
            metrics=_DIP_METRICS,
            anomalies=[],
            insights=[
                "April 8 revenue ($1,280) is 60% below the prior 7-day average ($3,200).",
                "PRD-003 (Laptop Stand) was out of stock — zero orders recorded.",
                "Weekend Social Boost campaign was paused, reducing social traffic.",
            ],
            comparison_period=_NORMAL_METRICS,
        )

    async def detect_revenue_anomalies(date_str: str = ""):
        return [
            Anomaly(
                metric="total_revenue", expected=3200.0, actual=1280.0, deviation_pct=-60.0, severity=Severity.HIGH
            ),
            Anomaly(metric="order_count", expected=22.0, actual=9.0, deviation_pct=-59.1, severity=Severity.HIGH),
        ]

    async def get_inventory_snapshot(as_of_date: str = ""):
        return InventoryAnalysis(
            kind="inventory",
            stock_levels=[
                StockLevel(
                    product=ProductRef(product_id="PRD-001", name="Wireless Headphones"),
                    quantity=450,
                    unit_price=149.99,
                    reorder_point=30,
                    days_until_stockout=None,
                    is_out_of_stock=False,
                ),
                StockLevel(
                    product=ProductRef(product_id="PRD-002", name="Running Shoes"),
                    quantity=12,
                    unit_price=119.99,
                    reorder_point=30,
                    days_until_stockout=3.5,
                    is_out_of_stock=False,
                ),
                StockLevel(
                    product=ProductRef(product_id="PRD-003", name="Laptop Stand"),
                    quantity=0,
                    unit_price=44.99,
                    reorder_point=30,
                    days_until_stockout=None,
                    is_out_of_stock=True,
                ),
                StockLevel(
                    product=ProductRef(product_id="PRD-004", name="USB-C Hub"),
                    quantity=200,
                    unit_price=34.99,
                    reorder_point=30,
                    days_until_stockout=None,
                    is_out_of_stock=False,
                ),
                StockLevel(
                    product=ProductRef(product_id="PRD-005", name="Yoga Mat"),
                    quantity=28,
                    unit_price=54.99,
                    reorder_point=30,
                    days_until_stockout=5.6,
                    is_out_of_stock=False,
                ),
            ],
            insights=[
                "Out of stock: Laptop Stand (PRD-003).",
                "Low stock (< 30 units): Running Shoes (PRD-002, 12 units), Yoga Mat (PRD-005, 28 units).",
            ],
        )

    async def get_stockout_impact(date_str: str = ""):
        return InventoryAnalysis(
            kind="inventory",
            stock_levels=[
                StockLevel(
                    product=ProductRef(product_id="PRD-003", name="Laptop Stand"),
                    quantity=0,
                    unit_price=44.99,
                    reorder_point=30,
                    days_until_stockout=None,
                    is_out_of_stock=True,
                ),
            ],
            stockout_missed_views=[ProductRef(product_id="PRD-003", name="Laptop Stand")],
            estimated_sales_impact=449.9,
            insights=[
                "PRD-003 (Laptop Stand) is out of stock — approximately $449.90 in revenue lost on April 8.",
            ],
        )

    async def get_campaign_status(start_date: str = ""):
        _spring_sale = Campaign(
            campaign_id="camp-1",
            name="Spring Sale",
            channel=Channel.EMAIL,
            status=CampaignStatus.ACTIVE,
            current_period=CampaignMetrics(spend=1800.0, impressions=82000, clicks=3280, conversions=164, roas=3.2),
            start_date=date(2026, 4, 1),
        )
        _weekend_boost = Campaign(
            campaign_id="camp-2",
            name="Weekend Social Boost",
            channel=Channel.SOCIAL,
            status=CampaignStatus.PAUSED,
            current_period=CampaignMetrics(spend=1200.0, impressions=45000, clicks=900, conversions=27, roas=1.1),
            start_date=date(2026, 4, 1),
        )
        _search_brand = Campaign(
            campaign_id="camp-3",
            name="Search Brand Keywords",
            channel=Channel.SEARCH,
            status=CampaignStatus.ACTIVE,
            current_period=CampaignMetrics(spend=2200.0, impressions=31000, clicks=1550, conversions=93, roas=2.8),
            start_date=date(2026, 4, 1),
        )
        return MarketingAnalysis(
            kind="marketing",
            campaigns=[_spring_sale, _weekend_boost, _search_brand],
            underperforming=[_weekend_boost],
            worst_channel=Channel.SOCIAL,
            insights=[
                "Weekend Social Boost campaign is PAUSED — reduced social traffic on April 8.",
                "Campaign 'Weekend Social Boost' has ROAS of 1.1 (below threshold of 1.5) and is currently paused.",
            ],
        )

    async def get_customer_support_snapshot(date_str: str = ""):
        return CustomerSupportAnalysis(
            kind="customer_support",
            period_tickets=18,
            previous_period_tickets=12,
            tickets_change_pct=50.0,
            refund_rate=0.15,
            return_rate=0.10,
            negative_reviews=5,
            common_issues=[
                CustomerComplaint(category="stock_availability", count=8, sample_texts=[], sentiment_score=-0.6),
                CustomerComplaint(category="delivery_delay", count=5, sample_texts=[], sentiment_score=-0.4),
            ],
            insights=[
                "50% spike in support tickets on April 8 vs. prior day.",
                "Stock availability complaints account for 44% of tickets — driven by PRD-003 stockout.",
            ],
        )

    async def search_past_incidents(query: str = "", limit: int = 3):
        from domains.memory.schemas import PastIncident, PastIncidentSearchResult

        return PastIncidentSearchResult(
            incidents=[
                PastIncident(
                    incident_id="hist-001",
                    query="Sales declined driven by Yoga Mat stockout and paused campaign",
                    summary="Yoga Mat (PRD-005) stockout coincided with paused Summer Promo campaign, "
                    "causing 35% revenue drop on March 15.",
                    actions_taken=["restock", "resume_campaign"],
                    similarity=0.82,
                    created_at=datetime(2026, 3, 16, 10, 0, 0, tzinfo=UTC),
                ),
            ]
        )

    mock_fns = [
        ("get_daily_sales_metrics", get_daily_sales_metrics),
        ("compare_sales_periods", compare_sales_periods),
        ("detect_revenue_anomalies", detect_revenue_anomalies),
        ("get_inventory_snapshot", get_inventory_snapshot),
        ("get_stockout_impact", get_stockout_impact),
        ("get_campaign_status", get_campaign_status),
        ("get_customer_support_snapshot", get_customer_support_snapshot),
        ("search_past_incidents", search_past_incidents),
    ]
    for name, fn in mock_fns:
        tool = StructuredTool.from_function(coroutine=fn, name=name, description=f"Mock {name}")
        registry._tools[name] = tool

    registry._enabled_domains = {"sales", "inventory", "marketing", "customer_support", "memory"}
    global _mcp_initialized
    _mcp_initialized = True


@pytest.fixture
def require_mcp():
    """Skip the current test if MCP registry initialisation failed or loaded no tools."""
    if not _mcp_initialized:
        pytest.skip(f"MCP unavailable ({_mcp_init_error}); skipping test that needs MCP tools.")
    import agents.mcp_registry as reg_module

    registry = reg_module._registry
    if registry is not None and not registry._tools:
        pytest.skip("MCP registry has no tools; skipping test that needs MCP tools.")


@pytest.fixture(autouse=True)
async def _reset_db_engine():
    """Reset the SQLAlchemy engine + session-factory before and after every async test.

    pytest-asyncio uses a function-scoped event loop by default.  asyncpg keeps
    open connections in the engine's pool that are bound to the *previous* test's
    event loop.  When that loop closes, those connections become unusable
    ('NoneType' has no attribute 'send').  Disposing the engine before each test
    ensures every test starts with a fresh pool on the current event loop.
    """
    import db.engine as engine_module
    import db.qdrant_store as qdrant_store_module
    import db.session as session_module

    # Tear down any leftover state from the previous test.
    engine_module._engine = None
    session_module._session_factory = None
    # QdrantClient (sync) holds an httpx connection — reset between tests.
    if qdrant_store_module._vector_store is not None:
        try:
            qdrant_store_module._vector_store.client.close()
        except Exception:
            pass
    qdrant_store_module._vector_store = None

    yield

    # Clean up after the test so the next one isn't handed dead connections.
    await engine_module.dispose_engine()
    session_module._session_factory = None
    if qdrant_store_module._vector_store is not None:
        try:
            qdrant_store_module._vector_store.client.close()
        except Exception:
            pass
    qdrant_store_module._vector_store = None


# ---------------------------------------------------------------------------
# DeepEval: custom judge LLM backed by Azure DIAL
# ---------------------------------------------------------------------------


def _make_dial_judge():
    """Build a DeepEvalBaseLLM judge using the project's Azure DIAL endpoint.

    Returns None if deepeval is not installed or settings are unavailable.
    """
    try:
        from deepeval.models import DeepEvalBaseLLM
        from langchain_openai import AzureChatOpenAI

        from core.settings import settings

        class DIALJudge(DeepEvalBaseLLM):
            """DeepEval judge backed by Azure DIAL (OpenAI-compatible)."""

            def load_model(self) -> AzureChatOpenAI:
                return AzureChatOpenAI(
                    azure_endpoint=settings.DIAL_ENDPOINT,
                    api_key=settings.DIAL_API_KEY,
                    api_version=settings.DIAL_API_VERSION,
                    azure_deployment=settings.DIAL_DEPLOYMENT,
                    temperature=0,
                )

            def generate(self, prompt: str, schema: type | None = None):
                model = self.load_model()
                if schema is not None:
                    return model.with_structured_output(schema).invoke(prompt)
                return model.invoke(prompt).content

            async def a_generate(self, prompt: str, schema: type | None = None):
                model = self.load_model()
                if schema is not None:
                    return await model.with_structured_output(schema).ainvoke(prompt)
                return (await model.ainvoke(prompt)).content

            def get_model_name(self) -> str:
                return f"DIAL/{settings.DIAL_DEPLOYMENT}"

        return DIALJudge()
    except Exception:
        return None


@pytest.fixture(scope="session")
def dial_judge():
    """Session-scoped DeepEval judge fixture. Skip eval tests if unavailable."""
    judge = _make_dial_judge()
    if judge is None:
        pytest.skip("DeepEval judge unavailable (missing deps or settings).")
    return judge


# ---------------------------------------------------------------------------
# API route test fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """httpx AsyncClient wired to the FastAPI app with a mocked graph."""
    from unittest.mock import AsyncMock

    from httpx import ASGITransport, AsyncClient

    from main import app

    app.state.graph = AsyncMock()
    app.state.checkpointer_type = "test"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
