"""Factory for creating vector store instances (simplified for Qdrant only)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .base import VectorStore
from .qdrant import QdrantVectorStore


def create_vector_store(
    cfg: Dict,
    repo_path: Path,
    collection_name: Optional[str] = None,
) -> VectorStore:
    if not collection_name:
        path_str = str(repo_path)
        if 'project/' in path_str:
            collection_name = path_str.split('project/')[-1]
        else:
            collection_name = repo_path.name
        
        import re
        collection_name = re.sub(r'[^a-zA-Z0-9_-]', '_', collection_name)
        if collection_name and not collection_name[0].isalpha() and collection_name[0] != '_':
            collection_name = '_' + collection_name
    
    vector_store_cfg = cfg.get("vector_store", {})
    qdrant_cfg = vector_store_cfg.get("qdrant", {})
    host = qdrant_cfg.get("host", "localhost")
    port = qdrant_cfg.get("port", 6333)
    
    return QdrantVectorStore(host=host, port=port, collection_name=collection_name)
