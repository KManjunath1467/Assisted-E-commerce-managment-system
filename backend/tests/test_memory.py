"""Memory layer tests — requires Qdrant running on localhost:6333.

Side-effect tests: these write to Qdrant. They use unique IDs and are safe
to run alongside read-only tests but should not be parallelised with each other.
"""

import pytest

from core.enums import ActionType
from db.qdrant_store import index_incident

pytestmark = pytest.mark.usefixtures("require_qdrant")


@pytest.mark.asyncio
async def test_index_incident_succeeds():
    """Indexing an incident into Qdrant should not raise."""
    test_id = "00000000-0000-0000-0000-000000000001"
    summary = "Sales declined 28% driven by Yoga Mat stockout and paused Social campaign"
    actions = [ActionType.RESTOCK, ActionType.RUN_DISCOUNT]

    await index_incident(incident_id=test_id, summary=summary, actions_taken=actions)


@pytest.mark.asyncio
async def test_index_incident_with_empty_actions():
    """Indexing with no actions should not raise."""
    test_id = "00000000-0000-0000-0000-000000000003"
    await index_incident(
        incident_id=test_id,
        summary="Minor ticket spike, no action required",
        actions_taken=[],
    )
