"""Core functionality for cursorlite."""

from .models import ChunkRecord
from .chunking import chunk_text, Chunker
from .embeddings import Embedder, SentenceTransformersEmbedder, make_embedder

__all__ = [
    "ChunkRecord",
    "chunk_text",
    "Chunker",
    "Embedder",
    "SentenceTransformersEmbedder",
    "make_embedder",
]
