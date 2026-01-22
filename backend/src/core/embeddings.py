"""Embedding models for semantic search."""

from __future__ import annotations

from typing import Dict, List


class Embedder:
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]


class SentenceTransformersEmbedder(Embedder):
    
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts using SentenceTransformers model."""
        arr = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [row.tolist() for row in arr]


def make_embedder(cfg: Dict) -> Embedder:
    backend = str(cfg.get("embedding", {}).get("backend", "sentence_transformers")).strip().lower()
    if backend != "sentence_transformers":
        raise SystemExit(f"embedding.backend không hợp lệ: {backend!r}")

    model_name = cfg.get("embedding", {}).get("sentence_transformers_model", "all-MiniLM-L6-v2")
    try:
        return SentenceTransformersEmbedder(model_name)
    except Exception as e:
        raise SystemExit(
            "Không load được sentence-transformers. "
            "Hãy chạy: pip install -U sentence-transformers"
        ) from e
