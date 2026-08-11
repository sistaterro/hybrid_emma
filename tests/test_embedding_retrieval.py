"""Tests for local embedding index validation and semantic ranking."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

import embedding_retrieval


class FakeEmbeddingModel:
    """Map fruit and policy terms onto deterministic vector dimensions."""

    def encode(self, texts, **_kwargs):
        """Create predictable vectors for retrieval assertions."""
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append([
                lowered.count("apple") + lowered.count("fruit"),
                lowered.count("vacation") + lowered.count("leave"),
                0.1,
            ])
        return np.asarray(vectors, dtype=float)


class EmbeddingRetrievalTests(unittest.TestCase):
    """Exercise persisted index integrity and global diversified retrieval."""

    def setUp(self):
        """Install the deterministic encoder."""
        embedding_retrieval.set_embedding_model(FakeEmbeddingModel())

    def test_index_metadata_detects_stale_chunks(self):
        """Reject an index after its source chunk text changes."""
        chunks = [{"id": "a:0000", "index": 0, "text": "apple fruit"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.npy"
            metadata = embedding_retrieval.write_embedding_index(path, chunks, "test-model")
            self.assertIsNotNone(embedding_retrieval.load_valid_embedding_index(path, chunks, metadata, "test-model"))
            changed = [{**chunks[0], "text": "vacation leave"}]
            self.assertIsNone(embedding_retrieval.load_valid_embedding_index(path, changed, metadata, "test-model"))

    def test_semantic_retrieval_ranks_globally_and_limits_each_source(self):
        """Prefer semantic matches while preserving multi-document diversity."""
        sources = [
            {
                "key": "global/fruit",
                "chunks": [{"index": 0, "text": "apple fruit"}, {"index": 1, "text": "apple apple fruit"}],
                "vectors": embedding_retrieval.encode_texts(["apple fruit", "apple apple fruit"], "test-model"),
            },
            {
                "key": "mine/leave",
                "chunks": [{"index": 0, "text": "vacation leave policy"}],
                "vectors": embedding_retrieval.encode_texts(["vacation leave policy"], "test-model"),
            },
        ]
        selected = embedding_retrieval.semantic_top_chunks("apple benefits", sources, 3, 1, "test-model")
        self.assertEqual([item["source_key"] for item in selected], ["global/fruit", "mine/leave"])
