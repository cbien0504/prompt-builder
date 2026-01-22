"""File utility functions."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re


def repo_root(start: Path) -> Path:
    """Find repo root by walking upward until .git exists, else current dir."""
    cur = start.resolve()
    for _ in range(50):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start.resolve()

def is_binary_file(path: Path) -> bool:
    """Check if file is binary by looking for null bytes."""
    try:
        with path.open("rb") as f:
            sample = f.read(2048)
        return b"\x00" in sample
    except Exception:
        return True


def file_sha256(path: Path) -> str:
    """Calculate SHA256 hash of file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def parse_query(query: str) -> Tuple[str, List[Dict[str, Optional[int]]]]:
    if not query:
        return "", []

    refs: List[Dict[str, Optional[int]]] = []

    def repl(match: re.Match) -> str:
        path = match.group("path")
        s = match.group("start")
        e = match.group("end")
        refs.append({
            "path": path,
            "start": int(s) if s else None,
            "end": int(e) if e else None,
        })
        return ""

    pattern = r"@(?P<path>[^\s:]+)(?::(?P<start>\d+)-(?P<end>\d+))?"
    clean = re.sub(pattern, repl, query)
    clean = " ".join(clean.split()).strip()
    return clean, refs