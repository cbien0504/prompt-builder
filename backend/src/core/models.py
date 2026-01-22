from __future__ import annotations

import dataclasses
from typing import List


@dataclasses.dataclass
class ChunkRecord:
    
    path: str
    start_line: int
    end_line: int
    file_hash: str
    chunk_hash: str
    text: str
    emb: List[float]