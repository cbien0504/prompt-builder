"""File utility functions."""

from __future__ import annotations

import hashlib
from pathlib import Path


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


def ensure_dir(p: Path) -> None:
    """Create directory if it doesn't exist."""
    p.mkdir(parents=True, exist_ok=True)


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


def get_sub_project_name(path: Path) -> str:
    import os
    project_root = Path(os.getenv("PROJECT_ROOT", "/project")).resolve()
    try:
        # Resolve path to ensure we have absolute path
        abs_path = path.resolve()
        
        # Try to extract relative to PROJECT_ROOT first
        if str(abs_path).startswith(str(project_root)):
            rel = abs_path.relative_to(project_root)
            # Get first part of relative path (subproject name)
            if len(rel.parts) > 0:
                return rel.parts[0]
                
        # Fallback: use the directory name itself
        # This handles cases where we are running locally or outside the standard structure
        val = abs_path.name
        if val:
            return val
            
    except Exception:
        pass
    return "default"
