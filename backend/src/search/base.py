"""Searcher Interface."""

from __future__ import annotations

from typing import Dict, List, Tuple
from pathlib import Path
from ..core import ChunkRecord


class Searcher:
    """Abstract base class for semantic search."""

    def search(
        self,
        repo: Path,
        cfg: Dict,
        query: str,
        top_k: int,
        scope: str = "subproject",
    ) -> List[Tuple[float, ChunkRecord]]:
        """Search for code chunks semantically similar to query.
        
        Args:
            repo: Repository root path
            cfg: Configuration dictionary
            query: Search query text
            top_k: Number of results to return
            scope: Search scope ("repo" or "subproject")
            
        Returns:
            List of (score, ChunkRecord) tuples sorted by relevance
        """
        raise NotImplementedError
