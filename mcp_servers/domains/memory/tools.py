"""Qdrant vector search tool for past incidents."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from functools import partial

from qdrant_client import AsyncQdrantClient, models
from sentence_transformers import SentenceTransformer
from settings import get_settings

from .schemas import PastIncident, PastIncidentSearchResult

logger = logging.getLogger(__name__)

COLLECTION = "incidents"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

_model: SentenceTransformer | None = None
_client: AsyncQdrantClient | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = AsyncQdrantClient(url=s.QDRANT_URL)
    return _client


def preload_model() -> None:
    """Pre-load the embedding model at startup (call from server.py)."""
    _get_model()
    logger.info("SentenceTransformer model '%s' pre-loaded", EMBEDDING_MODEL)


async def _encode_async(model: SentenceTransformer, text: str) -> list[float]:
    """Run model.encode in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()
    embedding = await loop.run_in_executor(None, partial(model.encode, text))
    return embedding.tolist()


async def search_past_incidents(query: str, limit: int = 3) -> PastIncidentSearchResult:
    """Search for past incidents similar to the given query.

    Uses Qdrant vector similarity search to find historically resolved incidents
    that are relevant to the current query, providing context for root-cause analysis.
    """
    try:
        client = _get_client()
        model = _get_model()
        embedding = await _encode_async(model, query)

        results = await client.query_points(
            collection_name=COLLECTION,
            query=embedding,
            limit=limit,
            with_payload=True,
        )

        incidents = []
        for point in results.points:
            raw_payload = point.payload or {}
            payload = raw_payload.get("metadata", raw_payload)
            raw_summary = payload.get("summary", "")
            summary_str = (
                ", ".join(raw_summary) if isinstance(raw_summary, list) else raw_summary
            )
            incidents.append(
                PastIncident(
                    incident_id=payload.get("incident_id", ""),
                    query=payload.get("query") or summary_str,
                    summary=summary_str,
                    actions_taken=[a for a in payload.get("actions_taken", [])],
                    similarity=float(point.score) if point.score is not None else 0.0,
                    created_at=(
                        datetime.fromisoformat(payload["created_at"])
                        if "created_at" in payload
                        else datetime.now(UTC)
                    ),
                )
            )

        return PastIncidentSearchResult(incidents=incidents)

    except Exception as exc:
        logger.warning("Qdrant search failed: %s", exc)
        return PastIncidentSearchResult(incidents=[])
