from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List


DEFAULT_INCLUDE_PATTERNS: List[str] = [
    "*.py", "*.js", "*.ts", "*.tsx", "*.jsx",
    "*.go", "*.java", "*.kt", "*.cs",
    "*.rb", "*.php", "*.rs",
    "*.c", "*.h", "*.cpp", "*.hpp",
    "*.swift",
    "*.txt", "*.yaml", "*.yml", "*.json",
]

DEFAULT_EXCLUDE_PATTERNS: List[str] = [
    ".git/**",
    "node_modules/**",
    "dist/**",
    "build/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    ".cursorlite/**",
    "target/**",
    ".next/**",
    ".idea/**",
    ".vscode/**",
    ".env",
    ".env.*",
]

DEFAULT_CONFIG: Dict = {
    "max_file_size_kb": 512,
    "chunk_max_tokens": 7000,
    "chunk_overlap_tokens": 200,
    "min_chunk_lines": 10,
    "embedding": {
        "backend": "sentence_transformers",
        "sentence_transformers_model": "sentence-transformers/all-MiniLM-L6-v2",
    },
    "search": {"top_k": 8},
    "run": {
        "test_command": []
    },
    "vector_store": {
        "backend": "qdrant",
        "qdrant": {
            "host": "localhost",
            "port": 6333,
        },
    },
}


def expand_pattern(pattern: str) -> List[str]:
    pattern = pattern.strip()
    if not pattern or pattern.startswith("#"):
        return []

    if pattern.startswith("**/"):
        return [pattern]

    if pattern.startswith("*."):
        return [pattern, "**/" + pattern]

    if "/**" in pattern:
        return [pattern, "**/" + pattern]

    return [pattern]


def _expand_patterns(patterns: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for p in patterns:
        for ep in expand_pattern(p):
            if ep not in seen:
                seen.add(ep)
                out.append(ep)
    return out


def load_config(repo: Path) -> Dict:
    config = dict(DEFAULT_CONFIG)
    
    config["vector_store"]["qdrant"]["host"] = os.getenv("QDRANT_HOST", "localhost")
    config["vector_store"]["qdrant"]["port"] = int(os.getenv("QDRANT_PORT", "6333"))
    
    config["include_globs"] = _expand_patterns(DEFAULT_INCLUDE_PATTERNS)
    config["exclude_globs"] = _expand_patterns(DEFAULT_EXCLUDE_PATTERNS)
    
    return config


def cfg_fingerprint(cfg: Dict) -> str:
    payload = json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
