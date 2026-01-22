
from __future__ import annotations

from typing import Dict, List, Tuple, Optional
import re

from .core import ChunkRecord, make_embedder
from .storage import make_vector_store
from .utils import parse_query

class Searcher():
    def search(
        self,
        cfg: Dict,
        query: str,
        top_k: int,
        collection_name: str,
    ) -> List[Tuple[float, ChunkRecord]]:
        clean_query, file_refs = parse_query(query)
        store = make_vector_store(cfg, collection_name=collection_name)
        self._ensure_collection_exists(store)

        emb = make_embedder(cfg)
        qv = emb.embed_one(clean_query or query)
        results = store.search(qv, top_k * 3, repo_filter=None)
        reranked = self._rerank(results, clean_query, file_refs)
        return reranked[:top_k]

    def _ensure_collection_exists(self, store) -> None:
        if store.exists():
            return
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
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Index not exists for collection '{store.collection_name}'")

    def _rerank(
        self,
        results: List[Tuple[float, ChunkRecord]],
        clean_query: str,
        file_refs: List[Dict[str, Optional[int]]],
    ) -> List[Tuple[float, ChunkRecord]]:
        keywords = set(clean_query.lower().split()) if clean_query else set()
        reranked: List[Tuple[float, ChunkRecord]] = []

        for score, record in results:
            boosted = score
            boosted += self._file_boost(record, file_refs)
            boosted += self._line_boost(record, file_refs)
            if keywords:
                text_lower = record.text.lower()
                kw_matches = sum(1 for kw in keywords if kw in text_lower)
                boosted += kw_matches * 0.1

            reranked.append((min(1.0, boosted), record))

        reranked.sort(key=lambda x: x[0], reverse=True)
        return reranked

    def _file_boost(self, record: ChunkRecord, file_refs: List[Dict[str, Optional[int]]]) -> float:
        if not file_refs:
            return 0.0
        rec_path = getattr(record, "path", None) or getattr(record, "file_path", None)
        if not rec_path:
            return 0.0
        for ref in file_refs:
            if self._path_matches(rec_path, ref.get("path")):
                return 0.5
        return 0.0

    def _line_boost(self, record: ChunkRecord, file_refs: List[Dict[str, Optional[int]]]) -> float:
        if not file_refs:
            return 0.0
        rec_path = getattr(record, "path", None) or getattr(record, "file_path", None)
        rec_start = getattr(record, "start_line", None)
        rec_end = getattr(record, "end_line", None)
        if rec_path is None or rec_start is None or rec_end is None:
            return 0.0

        for ref in file_refs:
            if ref.get("start") is None or ref.get("end") is None:
                continue
            if not self._path_matches(rec_path, ref.get("path")):
                continue
            if self._ranges_overlap(rec_start, rec_end, ref["start"], ref["end"]):
                return 0.3
        return 0.0

    @staticmethod
    def _path_matches(record_path: str, ref_path: Optional[str]) -> bool:
        if not ref_path:
            return False
        # basic match: exact or suffix match (in case user pastes relative path)
        return record_path == ref_path or record_path.endswith(ref_path)

    @staticmethod
    def _ranges_overlap(start1: int, end1: int, start2: int, end2: int) -> bool:
        return start1 <= end2 and start2 <= end1


def search(cfg: Dict, query: str, top_k: int, collection_name: str | None = None) -> List[Tuple[float, ChunkRecord]]:
    searcher = Searcher()
    return searcher.search(cfg, query, top_k, collection_name=collection_name)

def format_hit(score: float, r: ChunkRecord, max_chars: int = 1200) -> str:
    snippet = r.text
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars] + "\n…(truncated)…\n"
    header = f"{score:0.4f}  {r.path}:{r.start_line}-{r.end_line}"
    return header + "\n" + snippet.rstrip() + "\n"
