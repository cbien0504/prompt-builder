"""Core functionality for cursorlite."""

from .models import ChunkRecord
from .chunking import chunk_text, DefaultChunker
from .embeddings import Embedder, SentenceTransformersEmbedder, make_embedder

__all__ = [
    "ChunkRecord",
    "chunk_text",
    "DefaultChunker",
    "Embedder",
    "SentenceTransformersEmbedder",
    "make_embedder",
]
