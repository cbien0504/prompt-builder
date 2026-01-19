"""PromptBuilder Interface."""

from __future__ import annotations

from typing import List, Tuple
from ..core import ChunkRecord


class PromptBuilder:
    """Abstract base class for prompt building."""

    def build_prompt(
        self,
        task: str,
        hits: List[Tuple[float, ChunkRecord]],
        max_tokens: int = 40_000,
    ) -> Tuple[List[str], int]:
        """Build LLM prompt from search results.
        
        Args:
            task: User task description
            hits: List of search results (score, record)
            max_tokens: Maximum tokens for context
            
        Returns:
            Tuple of (list of prompt strings, total context tokens)
        """
        raise NotImplementedError
