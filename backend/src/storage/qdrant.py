"""Qdrant vector database backend."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import uuid
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from ..core.models import ChunkRecord
from .base import VectorStore

logger = logging.getLogger(__name__)


class QdrantVectorStore(VectorStore):
    
    def __init__(self, host: str = "localhost", port: int = 6333, collection_name: str = None):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.client = QdrantClient(host=host, port=port)
    
    def _get_collection_vector_dim(self) -> Optional[int]:
        collection_info = self.client.get_collection(collection_name=self.collection_name)
        return collection_info.config.params.vectors.size

    def _ensure_collection(self, vector_dim: int) -> None:
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE),
        )
    
    def save_records(self, records: List[ChunkRecord], metadata: Dict) -> None:
        if not records:
            logger.warning("No records to save")
            return
        
        vector_dim = len(records[0].emb) if records else 384
        
        for i, record in enumerate(records):
            if len(record.emb) != vector_dim:
                raise ValueError(
                    f"Record {i} at {record.path}:{record.start_line} has different dimension: "
                    f"{len(record.emb)} vs expected {vector_dim}"
                )
        
        existing_dim = self._get_collection_vector_dim()
        if existing_dim is not None and existing_dim != vector_dim:
            raise ValueError(
                f"Collection '{self.collection_name}' exists with dimension {existing_dim}, "
                f"but records have dimension {vector_dim}. Please delete the collection and re-index."
            )
        
        self._ensure_collection(vector_dim=vector_dim)
        
        repo_path = metadata.get("repo", "")
        if repo_path:
            try:
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="repo",
                                match=MatchValue(value=repo_path)
                            )
                        ]
                    )
                )
                logger.info(f"Cleared old records for repo: {repo_path}")
            except Exception as e:
                logger.warning(f"Error clearing old records for {repo_path}: {e}")
        
        points = []
        for _, record in enumerate(records):
            payload = {
                "path": record.path,
                "start_line": record.start_line,
                "end_line": record.end_line,
                "file_hash": record.file_hash,
                "chunk_hash": record.chunk_hash,
                "text": record.text,
                # Metadata
                "repo": metadata.get("repo", ""),
                "subproject": metadata.get("subproject", ""),
                "created_at": metadata.get("created_at", ""),
                "cfg_fingerprint": metadata.get("cfg_fingerprint", ""),
            }
            
            point_id = str(uuid.uuid4())
            
            points.append(
                PointStruct(
                    id=point_id,
                    vector=record.emb,
                    payload=payload,
                )
            )
        
        batch_size = 100
        total_batches = (len(points) + batch_size - 1) // batch_size
        logger.info(f"Uploading {len(points)} points in {total_batches} batches")
        
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            batch_num = i // batch_size + 1
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch,
                )
                logger.debug(f"Uploaded batch {batch_num}/{total_batches}")
            except Exception as e:
                raise RuntimeError(
                    f"Failed to upsert batch {batch_num}/{total_batches} "
                    f"(points {i}-{i+len(batch)}): {e}"
                ) from e
        
        logger.info(f"Successfully saved {len(points)} records to collection '{self.collection_name}'")
    
    def load_records(self, repo_filter: Optional[str] = None) -> Tuple[List[ChunkRecord], Dict]:
        """Load all records from Qdrant."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        records = []
        metadata = {}
        
        offset = None
        limit = 100
        
        scroll_filter = None
        if repo_filter:
             scroll_filter = Filter(
                 must=[FieldCondition(key="repo", match=MatchValue(value=repo_filter))]
             )
        
        while True:
            result = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            
            points, next_offset = result
            
            if not points:
                break
            
            for point in points:
                payload = point.payload
                
                # Extract metadata from first record
                if not metadata:
                    metadata = {
                        "repo": payload.get("repo", ""),
                        "subproject": payload.get("subproject", ""),
                        "created_at": payload.get("created_at", ""),
                        "cfg_fingerprint": payload.get("cfg_fingerprint", ""),
                    }
                
                record = ChunkRecord(
                    path=payload["path"],
                    start_line=payload["start_line"],
                    end_line=payload["end_line"],
                    file_hash=payload["file_hash"],
                    chunk_hash=payload["chunk_hash"],
                    text=payload["text"],
                    emb=point.vector,
                )
                records.append(record)
            
            if next_offset is None:
                break
            offset = next_offset
        
        return records, metadata
    
    def search(self, query_vector: List[float], top_k: int, repo_filter: Optional[str] = None) -> List[Tuple[float, ChunkRecord]]:
        """Search using Qdrant's vector search."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        search_filter = None
        if repo_filter:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="repo",
                        match=MatchValue(value=repo_filter)
                    )
                ]
            )
        
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                query_filter=search_filter,
                with_payload=True,
                with_vectors=False,
            )
            
            hits = []
            for result in results.points:
                payload = result.payload
                score = result.score
                
                record = ChunkRecord(
                    path=payload["path"],
                    start_line=payload["start_line"],
                    end_line=payload["end_line"],
                    file_hash=payload["file_hash"],
                    chunk_hash=payload["chunk_hash"],
                    text=payload["text"],
                    emb=[],  # Not needed for search results
                )
                hits.append((score, record))
            
            return hits
            
        except Exception as e:
            logger.error(f"Error searching in collection '{self.collection_name}': {e}")
            raise
    
    def get_metadata(self, repo_filter: Optional[str] = None) -> Optional[Dict]:
        """Get metadata from first record."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        scroll_filter = None
        if repo_filter:
            scroll_filter = Filter(
                must=[FieldCondition(key="repo", match=MatchValue(value=repo_filter))]
            )
        
        try:
            result = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
            
            points, _ = result
            if not points:
                return None
            
            payload = points[0].payload
            return {
                "repo": payload.get("repo", ""),
                "subproject": payload.get("subproject", ""),
                "created_at": payload.get("created_at", ""),
                "cfg_fingerprint": payload.get("cfg_fingerprint", ""),
            }
        except Exception as e:
            logger.error(f"Error getting metadata from collection '{self.collection_name}': {e}")
            return None
    
    def clear(self) -> None:
        """Delete all records in collection."""
        try:
            self.client.delete_collection(collection_name=self.collection_name)
            # Recreate empty collection
            info = self.client.get_collection(collection_name=self.collection_name)
            vector_dim = info.config.params.vectors.size
            self._ensure_collection(vector_dim=vector_dim)
        except Exception:
            pass
    
    def exists(self) -> bool:
        """Check if collection exists and has data."""
        try:
            info = self.client.get_collection(collection_name=self.collection_name)
            return info.points_count > 0
        except Exception:
            return False
    
    def delete_by_filter(self, repo_filter: str) -> None:
        """Delete records matching the repo filter."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="repo",
                            match=MatchValue(value=repo_filter)
                        )
                    ]
                )
            )
            logger.info(f"Deleted records for repo: {repo_filter}")
        except Exception as e:
            logger.error(f"Error deleting records for {repo_filter}: {e}")
            raise
    
    def count(self, repo_filter: Optional[str] = None) -> int:
        """Count records in the collection."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue, CountRequest
        
        try:
            if repo_filter:
                # Count with filter
                result = self.client.count(
                    collection_name=self.collection_name,
                    count_filter=Filter(
                        must=[
                            FieldCondition(
                                key="repo",
                                match=MatchValue(value=repo_filter)
                            )
                        ]
                    )
                )
                return result.count
            else:
                # Count all
                info = self.client.get_collection(collection_name=self.collection_name)
                return info.points_count
        except Exception:
            return 0
    
    def list_collections(self) -> List[str]:
        """List all collections in Qdrant."""
        try:
            collections = self.client.get_collections().collections
            return [c.name for c in collections]
        except Exception:
            return []


def make_vector_store(cfg: Dict, collection_name: str) -> VectorStore:
    
    vector_store_cfg = cfg.get("vector_store", {})
    qdrant_cfg = vector_store_cfg.get("qdrant", {})
    host = qdrant_cfg.get("host", "localhost")
    port = qdrant_cfg.get("port", 6333)
    
    return QdrantVectorStore(host=host, port=port, collection_name=collection_name)
