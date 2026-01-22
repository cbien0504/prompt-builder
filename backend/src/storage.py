from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from .core.models import ChunkRecord

logger = logging.getLogger(__name__)


class QdrantClientWrapper:

    def __init__(self, host: str = "localhost", port: int = 6333):
        self.host = host
        self.port = port
        self.client = QdrantClient(host=host, port=port)


class VectorStore:

    def __init__(self, client: QdrantClientWrapper, collection_name: str):
        self._client = client
        self.collection_name = collection_name

    @property
    def client(self) -> QdrantClient:
        return self._client.client

    def _ensure_collection(self, vector_dim: int) -> None:
        try:
            self.client.get_collection(collection_name=self.collection_name)
            return
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE),
            )

    def exists(self) -> bool:
        try:
            info = self.client.get_collection(collection_name=self.collection_name)
            return bool(getattr(info, "points_count", 0))
        except Exception:
            return False

    def clear(self) -> None:
        try:
            self.client.delete_collection(collection_name=self.collection_name)
        except Exception as e:
            logger.warning(f"Error clearing collection '{self.collection_name}': {e}")

    def save_records(self, records: List[ChunkRecord], metadata: Dict) -> None:
        if not records:
            logger.warning("No records to save")
            return

        vector_dim = len(records[0].emb) if records[0].emb is not None else 0
        if vector_dim <= 0:
            raise ValueError("Records must contain embeddings (non-empty 'emb').")

        self._ensure_collection(vector_dim=vector_dim)

        repo_path = metadata.get("repo")
        if repo_path:
            try:
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=Filter(
                        must=[FieldCondition(key="repo", match=MatchValue(value=repo_path))]
                    ),
                )
            except Exception as exc:
                logger.warning(f"Failed clearing old records for repo={repo_path}: {exc}")

        points: List[PointStruct] = []
        for r in records:
            payload = {
                "path": r.path,
                "start_line": r.start_line,
                "end_line": r.end_line,
                "file_hash": r.file_hash,
                "chunk_hash": r.chunk_hash,
                "text": r.text,
                "repo": metadata.get("repo", ""),
                "subproject": metadata.get("subproject", ""),
                "created_at": metadata.get("created_at", ""),
                "cfg_fingerprint": metadata.get("cfg_fingerprint", ""),
            }
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=r.emb,
                    payload=payload,
                )
            )

        batch_size = 128
        for i in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[i : i + batch_size],
            )

    def load_records(self, repo_filter: Optional[str] = None) -> Tuple[List[ChunkRecord], Dict]:
        records: List[ChunkRecord] = []
        metadata: Dict = {}

        qfilter = None
        if repo_filter:
            qfilter = Filter(
                must=[FieldCondition(key="repo", match=MatchValue(value=repo_filter))]
            )

        offset = None
        while True:
            points, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=qfilter,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            for p in points:
                payload = p.payload or {}
                if not metadata and payload:
                    metadata = {
                        "repo": payload.get("repo", ""),
                        "subproject": payload.get("subproject", ""),
                        "created_at": payload.get("created_at", ""),
                        "cfg_fingerprint": payload.get("cfg_fingerprint", ""),
                    }
                records.append(
                    ChunkRecord(
                        path=payload.get("path", ""),
                        start_line=int(payload.get("start_line", 0)),
                        end_line=int(payload.get("end_line", 0)),
                        file_hash=payload.get("file_hash", ""),
                        chunk_hash=payload.get("chunk_hash", ""),
                        text=payload.get("text", ""),
                        emb=list(getattr(p, "vector", []) or []),
                    )
                )

            if next_offset is None:
                break
            offset = next_offset

        return records, metadata

    def get_metadata(self, repo_filter: Optional[str] = None) -> Optional[Dict]:
        try:
            _, meta = self.load_records(repo_filter=repo_filter)
            return meta or None
        except Exception:
            return None

    def search(
        self, query_vector: List[float], top_k: int, repo_filter: Optional[str] = None
    ) -> List[Tuple[float, ChunkRecord]]:
        qfilter = None
        if repo_filter:
            qfilter = Filter(
                must=[FieldCondition(key="repo", match=MatchValue(value=repo_filter))]
            )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
            query_filter=qfilter,
        )

        hits: List[Tuple[float, ChunkRecord]] = []
        for result in getattr(results, "points", []) or []:
            payload = result.payload or {}
            score = getattr(result, "score", 0.0)
            record = ChunkRecord(
                path=payload.get("path", ""),
                start_line=int(payload.get("start_line", 0)),
                end_line=int(payload.get("end_line", 0)),
                file_hash=payload.get("file_hash", ""),
                chunk_hash=payload.get("chunk_hash", ""),
                text=payload.get("text", ""),
                emb=[],
            )
            hits.append((score, record))
        return hits


def _collection_name_from_repo_path(repo_path: Path) -> str:
    name = repo_path.name
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    if name and not name[0].isalpha() and name[0] != "_":
        name = "_" + name
    return name


def make_vector_store(cfg: Dict, collection_name: str) -> VectorStore:
    qdrant_cfg = cfg.get("vector_store", {}).get("qdrant", {})
    host = qdrant_cfg.get("host", "localhost")
    port = qdrant_cfg.get("port", 6333)
    client = QdrantClientWrapper(host=host, port=port)
    return VectorStore(client=client, collection_name=collection_name)


def create_vector_store(
    cfg: Dict, repo_path: Path, collection_name: Optional[str] = None
) -> VectorStore:
    return make_vector_store(cfg, collection_name or _collection_name_from_repo_path(repo_path))


__all__ = ["QdrantClientWrapper", "VectorStore", "make_vector_store", "create_vector_store"]
