"""Abstract vector storage interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from ..core.models import ChunkRecord


class VectorStore(ABC):
    """Abstract base class for vector storage backends."""
    
    @abstractmethod
    def save_records(self, records: List[ChunkRecord], metadata: Dict) -> None:
        """Save records to the vector store."""
        pass
    
    @abstractmethod
    def load_records(self, repo_filter: Optional[str] = None) -> Tuple[List[ChunkRecord], Dict]:
        """Load records from the vector store."""
        pass
    
    @abstractmethod
    def search(
        self, 
        query_vector: List[float], 
        top_k: int, 
        repo_filter: Optional[str] = None
    ) -> List[Tuple[float, ChunkRecord]]:
        """Search for similar records."""
        pass
    
    @abstractmethod
    def get_metadata(self, repo_filter: Optional[str] = None) -> Optional[Dict]:
        """Get metadata from the vector store."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all records in the collection."""
        pass
    
    @abstractmethod
    def exists(self) -> bool:
        """Check if collection exists and has data."""
        pass
    
    def delete_by_filter(self, repo_filter: str) -> None:
        """Delete records matching the filter (default implementation)."""
        all_records, metadata = self.load_records()
        filtered_records = [r for r in all_records if metadata.get("repo") != repo_filter]
        self.clear()
        if filtered_records:
            self.save_records(filtered_records, metadata)
    
    def count(self, repo_filter: Optional[str] = None) -> int:
        """Count records in the collection (default implementation)."""
        records, _ = self.load_records(repo_filter=repo_filter)
        return len(records)
