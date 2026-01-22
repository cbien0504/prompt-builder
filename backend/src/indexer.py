
from __future__ import annotations

import datetime as _dt
import fnmatch
import hashlib
from pathlib import Path
from typing import Dict, Iterable, List
from .web.models import Folder
from sqlalchemy.orm import Session

from .config import DEFAULT_EXCLUDE_PATTERNS, DEFAULT_INCLUDE_PATTERNS, cfg_fingerprint, _expand_patterns
from .core import ChunkRecord, make_embedder, Chunker
from .storage import create_vector_store
from .utils import file_sha256, is_binary_file


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


class Indexer():
    def index(
        self,
        repo: Path,
        cfg: Dict,
    ) -> int:
        emb = make_embedder(cfg)
        store = create_vector_store(cfg, repo)

        repo_str = str(repo)
        cfg_fp = cfg_fingerprint(cfg)

        prev_metadata = store.get_metadata(repo_filter=repo_str)
        prev_cfg_fp = prev_metadata.get("cfg_fingerprint") if prev_metadata else None

        prev_map: Dict[str, List[ChunkRecord]] = {}
        if prev_metadata and prev_cfg_fp == cfg_fp:
            prev_records, _ = store.load_records(repo_filter=repo_str)
            for r in prev_records:
                prev_map.setdefault(r.path, []).append(r)

        max_tokens = int(cfg.get("chunk_max_tokens", 7000))
        overlap = int(cfg.get("chunk_overlap_tokens", 200))
        min_lines = int(cfg.get("min_chunk_lines", 10))
        chunker = Chunker(max_tokens=max_tokens, overlap=overlap, min_lines=min_lines)

        records: List[ChunkRecord] = []
        seen_files: set[str] = set()
        changed = False

        for fp in iter_files(repo, cfg):
            rel = fp.relative_to(repo).as_posix()
            seen_files.add(rel)
            fhash = file_sha256(fp)

            if rel in prev_map and prev_map[rel] and prev_map[rel][0].file_hash == fhash:
                records.extend(prev_map[rel])
                continue

            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lines = text.splitlines(keepends=True)
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

        deleted = bool(prev_map) and (set(prev_map.keys()) != seen_files)
        if prev_metadata and prev_cfg_fp == cfg_fp and not changed and not deleted:
            return 0

        metadata = {
            "repo": repo_str,
            "created_at": _dt.datetime.utcnow().isoformat() + "Z",
            "cfg_fingerprint": cfg_fp,
        }

        store.save_records(records, metadata)
        return len(records)


def build_index(
    db: Session,
    repo: Path,
    cfg: Dict,
) -> None:

    folder = db.query(Folder).filter(Folder.path == str(repo)).first()

    if folder:
        folder.status = "indexing"
        folder.error_message = None
        db.commit()

    try:
        indexer = Indexer()
        total_chunks = indexer.index(repo, cfg)
        if folder:
            if total_chunks > 0:
                folder.status = "indexed"
                folder.error_message = None
                folder.total_chunks = total_chunks
                folder.last_indexed_at = _dt.datetime.utcnow()
                db.commit()
            else:
                folder.status = "error"
                folder.error_message = "No chunks indexed"
                db.commit()
    except Exception as e:
        if folder:
            folder.status = "error"
            folder.error_message = str(e)
            db.commit()
        raise
