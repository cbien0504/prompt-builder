"""Code indexing logic."""

from __future__ import annotations

import datetime as _dt
import fnmatch
import hashlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..config import cfg_fingerprint, DEFAULT_INCLUDE_PATTERNS, DEFAULT_EXCLUDE_PATTERNS
from ..config.manager import _expand_patterns
from ..core import ChunkRecord, chunk_text, make_embedder
from ..storage import make_vector_store
from ..utils import file_sha256, is_binary_file


def _match_any(path: str, globs: List[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def iter_files(repo: Path, cfg: Dict) -> Iterable[Path]:
    include_globs = cfg.get("include_globs", _expand_patterns(DEFAULT_INCLUDE_PATTERNS))
    exclude_globs = cfg.get("exclude_globs", _expand_patterns(DEFAULT_EXCLUDE_PATTERNS))
    max_kb = int(cfg.get("max_file_size_kb", 512))

    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(repo).as_posix()
        if _match_any(rel, exclude_globs):
            continue
        if not _match_any(rel, include_globs):
            continue
        try:
            if (p.stat().st_size / 1024.0) > max_kb:
                continue
        except Exception:
            continue
        if is_binary_file(p):
            continue
        yield p


from .base import Indexer

class DefaultIndexer(Indexer):

    def index(self, repo: Path, cfg: Dict, incremental: bool = True, collection_name: Optional[str] = None) -> None:
        emb = make_embedder(cfg)
        
        store = make_vector_store(cfg, collection_name=collection_name)
        repo_str = str(repo)
        prev_metadata = store.get_metadata(repo_filter=repo_str) if incremental else None

        prev_map: Dict[str, List[ChunkRecord]] = {}
        prev_cfg_fp = prev_metadata.get("cfg_fingerprint") if prev_metadata else None
        cfg_fp = cfg_fingerprint(cfg)

        if prev_metadata and prev_cfg_fp == cfg_fp:
            prev_records, _ = store.load_records(repo_filter=repo_str)
            for r in prev_records:
                prev_map.setdefault(r.path, []).append(r)

        records: List[ChunkRecord] = []

        max_tokens = int(cfg.get("chunk_max_tokens", 7000))
        overlap = int(cfg.get("chunk_overlap_tokens", 200))
        min_lines = int(cfg.get("min_chunk_lines", 10))
        
        # Initialize Chunker
        from ..core import DefaultChunker
        chunker = DefaultChunker(max_tokens=max_tokens, overlap=overlap, min_lines=min_lines)

        for fp in iter_files(repo, cfg):
            rel = fp.relative_to(repo).as_posix()
            fhash = file_sha256(fp)

            if incremental and rel in prev_map:
                if prev_map[rel] and prev_map[rel][0].file_hash == fhash:
                    records.extend(prev_map[rel])
                    continue

            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = text.splitlines(keepends=True)
            # Use chunker instance
            chunks = chunker.chunk(lines, file_path=str(fp))
            chunk_texts = [c[2] for c in chunks]
            if not chunk_texts:
                continue

            chunk_embs = emb.embed(chunk_texts)
            for (sline, eline, ctext), v in zip(chunks, chunk_embs):
                ch = hashlib.sha256(
                    (rel + ":" + str(sline) + ":" + str(eline) + ":" + fhash).encode("utf-8")
                ).hexdigest()
                records.append(
                    ChunkRecord(
                        path=rel,
                        start_line=sline,
                        end_line=eline,
                        file_hash=fhash,
                        chunk_hash=ch,
                        text=ctext,
                        emb=v,
                    )
                )

        # Save to vector store
        # Extract subproject name for metadata
        from ..utils.file_utils import get_sub_project_name
        subproject_name = get_sub_project_name(repo)
        
        metadata = {
            "repo": str(repo),
            "subproject": subproject_name,
            "created_at": _dt.datetime.utcnow().isoformat() + "Z",
            "cfg_fingerprint": cfg_fp,
        }
        
        store.save_records(records, metadata)
        print(f"Indexed {len(records)} chunks into Qdrant")


def build_index(repo: Path, cfg: Dict, incremental: bool = True, collection_name: Optional[str] = None) -> None:
    """Build or update code index (Wrapper)."""
    indexer = DefaultIndexer()
    indexer.index(repo, cfg, incremental=incremental, collection_name=collection_name)
