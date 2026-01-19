"""Indexer Interface."""

from __future__ import annotations

from typing import Dict, Optional
from pathlib import Path


class Indexer:
    """Abstract base class for code indexing."""

    def index(self, repo: Path, cfg: Dict, incremental: bool = True, collection_name: Optional[str] = None) -> None:
        raise NotImplementedError
