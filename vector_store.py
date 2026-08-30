"""Persistent ChromaDB storage for Emma RAG chunks."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any


DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_COLLECTION_NAME = "emma_rag_chunks"


def vector_db_path() -> Path:
    """Return the configured persistent ChromaDB directory."""
    return Path(os.getenv("EMMA_VECTOR_DB_PATH", "chroma_db"))


def embedding_model_name() -> str:
    """Return the configured Sentence Transformers embedding model."""
    return os.getenv("EMMA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def get_collection():
    """Open the persistent Emma ChromaDB collection."""
    import chromadb
    from chromadb.utils import embedding_functions

    client = chromadb.PersistentClient(path=str(vector_db_path()))
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=embedding_model_name()
    )
    return client.get_or_create_collection(
        name=DEFAULT_COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"embedding_model": embedding_model_name()},
    )


def chunk_id(scope: str, owner_id: int | None, stem: str, index: int) -> str:
    """Build a deterministic, collision-resistant ID for one RAG chunk."""
    owner = "global" if owner_id is None else str(owner_id)
    raw = f"{scope}:{owner}:{stem}:{index:04d}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{scope}/{owner}/{stem}/{index:04d}-{digest}"


def add_rag_chunks(
    chunks: list[dict[str, Any]],
    *,
    security_risk: str = "none",
) -> list[str]:
    """Insert chunk documents and metadata into persistent ChromaDB."""
    if not chunks:
        return []
    collection = get_collection()
    ids = []
    documents = []
    metadatas = []
    for chunk in chunks:
        scope = str(chunk.get("scope", "user"))
        owner_id = chunk.get("owner_id")
        stem = str(chunk.get("id", "chunk")).split(":", 1)[0]
        index = int(chunk.get("index", len(ids)))
        text = str(chunk.get("text", "")).strip()
        if not text:
            continue
        ids.append(chunk_id(scope, owner_id, stem, index))
        documents.append(text)
        metadatas.append(
            {
                "scope": scope,
                "owner_id": "global" if owner_id is None else str(owner_id),
                "stem": stem,
                "source": str(chunk.get("source", "")),
                "chunk_index": index,
                "security_risk": security_risk,
                "embedding_model": embedding_model_name(),
            }
        )
    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return ids


def delete_rag_chunks(scope: str, owner_id: int | None, stem: str) -> None:
    """Delete all persisted vectors belonging to one RAG."""
    collection = get_collection()
    owner = "global" if owner_id is None else str(owner_id)
    collection.delete(where={"$and": [{"scope": scope}, {"owner_id": owner}, {"stem": stem}]})

