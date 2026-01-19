"""Semantic search functionality."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple, Optional

from ..core import ChunkRecord, make_embedder
from ..storage import make_vector_store
from ..utils.file_utils import get_sub_project_name
import re

from .base import Searcher

class DefaultSearcher(Searcher):
    
    def search(
        self,
        repo: Path,
        cfg: Dict,
        query: str,
        top_k: int,
        collection_name: Optional[str] = None,
    ) -> List[Tuple[float, ChunkRecord]]:
        if not collection_name:
            repo_name = get_sub_project_name(repo)
            clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', repo_name)
            collection_name = clean_name
        
        store = make_vector_store(cfg, repo, collection_name=collection_name)
        
        if not store.exists():
            try:
                info = store.client.get_collection(collection_name=store.collection_name)
                if info.points_count == 0:
                    raise ValueError(
                        f"Collection '{store.collection_name}' exists but is empty (0 points). "
                        f"Please run indexing first."
                    )
            except Exception as e:
                error_msg = str(e).lower()
                if "not found" in error_msg or "does not exist" in error_msg:
                    raise ValueError(
                        f"Collection '{store.collection_name}' not found. "
                        f"Please run indexing first."
                    )
                # Re-raise if it's already a ValueError
                if isinstance(e, ValueError):
                    raise
            raise ValueError(f"Index not exists for collection '{store.collection_name}'")
        
        emb = make_embedder(cfg)
        qv = emb.embed_one(query)
        results = store.search(qv, top_k * 3, repo_filter=None)
        query_keywords = set(query.lower().split())
        reranked = []
        
        for score, record in results:
            text_lower = record.text.lower()
            keyword_matches = sum(1 for kw in query_keywords if kw in text_lower)
            keyword_boost = keyword_matches * 0.1
            boosted_score = min(1.0, score + keyword_boost)
            reranked.append((boosted_score, record))
        reranked.sort(key=lambda x: x[0], reverse=True)
        return reranked[:top_k]


def search(repo: Path, cfg: Dict, query: str, top_k: int, collection_name: str | None = None) -> List[Tuple[float, ChunkRecord]]:
    searcher = DefaultSearcher()
    return searcher.search(repo, cfg, query, top_k, collection_name=collection_name)


def format_hit(score: float, r: ChunkRecord, max_chars: int = 1200) -> str:
    snippet = r.text
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars] + "\n…(truncated)…\n"
    header = f"{score:0.4f}  {r.path}:{r.start_line}-{r.end_line}"
    return header + "\n" + snippet.rstrip() + "\n"
