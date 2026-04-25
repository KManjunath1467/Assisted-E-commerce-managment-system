"""Qdrant incident indexing for the memory layer."""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_qdrant import QdrantVectorStore

from core.enums import ActionType
from core.settings import settings

COLLECTION = "incidents"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

_vector_store: QdrantVectorStore | None = None


def _get_vector_store() -> QdrantVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = QdrantVectorStore.construct_instance(
            embedding=FastEmbedEmbeddings(model_name=EMBEDDING_MODEL),
            collection_name=COLLECTION,
            client_options={"url": settings.QDRANT_URL},
            validate_collection_config=False,
        )
    return _vector_store


async def index_incident(
    incident_id: str,
    summary: str,
    actions_taken: list[ActionType],
    query: str = "",
    created_at: datetime | None = None,
) -> None:
    """Upsert incident embedding into Qdrant."""
    store = _get_vector_store()
    doc = f"{summary}. Actions taken: {', '.join(a.value for a in actions_taken)}" if actions_taken else summary
    metadata = {
        "incident_id": incident_id,
        "summary": summary,
        "query": query,
        "actions_taken": [a.value for a in actions_taken],
        "created_at": (created_at or datetime.now(UTC)).isoformat(),
    }
    await store.aadd_texts([doc], metadatas=[metadata], ids=[incident_id])
