"""Local embedding indexing and semantic RAG retrieval policies."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Iterable

import numpy as np

DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
_embedding_model = None
_model_lock = Lock()


def get_embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL):
    """Load and cache the local Sentence Transformers model on first use."""
    global _embedding_model
    if _embedding_model is None:
        with _model_lock:
            if _embedding_model is None:
                from sentence_transformers import SentenceTransformer

                _embedding_model = SentenceTransformer(model_name)
    return _embedding_model


def set_embedding_model(model) -> None:
    """Override the cached encoder, primarily for deterministic tests."""
    global _embedding_model
    _embedding_model = model


def chunk_fingerprint(chunks: Iterable[dict]) -> str:
    """Return a stable digest that binds an embedding index to its chunks."""
    digest = sha256()
    for chunk in chunks:
        digest.update(str(chunk.get("id", "")).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(chunk.get("text", "")).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def encode_texts(texts: list[str], model_name: str = DEFAULT_EMBEDDING_MODEL) -> np.ndarray:
    """Encode text locally and return normalized float32 vectors."""
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    vectors = np.asarray(get_embedding_model(model_name).encode(texts, show_progress_bar=False), dtype=np.float32)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


def write_embedding_index(path: Path, chunks: list[dict], model_name: str) -> dict:
    """Encode chunks, persist their vectors, and return index metadata."""
    vectors = encode_texts([str(chunk.get("text", "")) for chunk in chunks], model_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(path), vectors)
    return {
        "model": model_name,
        "dimensions": int(vectors.shape[1]) if vectors.ndim == 2 and len(vectors) else 0,
        "count": len(chunks),
        "chunk_fingerprint": chunk_fingerprint(chunks),
    }


def load_valid_embedding_index(path: Path, chunks: list[dict], metadata: dict, model_name: str) -> np.ndarray | None:
    """Load vectors only when metadata proves they match the current chunks."""
    if not path.exists() or not isinstance(metadata, dict):
        return None
    if metadata.get("model") != model_name or metadata.get("chunk_fingerprint") != chunk_fingerprint(chunks):
        return None
    try:
        vectors = np.asarray(np.load(str(path), allow_pickle=False), dtype=np.float32)
    except (OSError, ValueError):
        return None
    if vectors.ndim != 2 or len(vectors) != len(chunks):
        return None
    if int(metadata.get("dimensions", -1)) != vectors.shape[1]:
        return None
    return vectors


def semantic_top_chunks(question: str, sources: list[dict], top_k: int, max_per_source: int, model_name: str = DEFAULT_EMBEDDING_MODEL) -> list[dict]:
    """Rank chunks globally by cosine similarity with per-source diversity."""
    if not question.strip() or top_k < 1:
        return []
    query = encode_texts([question], model_name)[0]
    ranked = []
    for source in sources:
        vectors = source.get("vectors")
        chunks = source.get("chunks", [])
        if not isinstance(vectors, np.ndarray) or vectors.ndim != 2 or len(vectors) != len(chunks):
            continue
        for index, score in enumerate(vectors @ query):
            chunk = chunks[index]
            if str(chunk.get("text", "")).strip():
                ranked.append({**chunk, "source_key": source["key"], "score": float(score)})
    ranked.sort(key=lambda item: (-item["score"], item["source_key"], int(item.get("index", 0))))
    selected = []
    per_source: dict[str, int] = {}
    for chunk in ranked:
        key = chunk["source_key"]
        if per_source.get(key, 0) >= max_per_source:
            continue
        selected.append(chunk)
        per_source[key] = per_source.get(key, 0) + 1
        if len(selected) >= top_k:
            break
    return selected
