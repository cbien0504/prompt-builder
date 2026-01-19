"""Pydantic schemas for API requests/responses."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class FolderBase(BaseModel):
    """Base folder schema."""
    path: str
    name: str


class FolderCreate(BaseModel):
    """Schema for creating a folder."""
    path: str


class FolderResponse(BaseModel):
    """Schema for folder response."""
    id: int
    path: str
    name: str
    status: str
    repo_count: int = 0  # Number of repositories in subproject
    total_files: int
    indexed_files: int
    total_chunks: int
    last_indexed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str]

    class Config:
        from_attributes = True


class IndexRequest(BaseModel):
    """Schema for indexing request."""
    incremental: bool = True


class SearchRequest(BaseModel):
    query: str
    folder_id: int
    top_k: int = 10


class SearchResult(BaseModel):
    """Schema for search result."""
    folder_id: int
    folder_name: str
    file_path: str
    start_line: int
    end_line: int
    score: float
    text: str


class SearchResponse(BaseModel):
    """Schema for search response."""
    results: List[SearchResult]


class ContextRequest(BaseModel):
    """Schema for context generation request."""
    task: str
    folder_ids: Optional[List[int]] = None
    top_k: int = 10


class ContextResponse(BaseModel):
    """Schema for context response."""
    prompts: List[str]
    total_tokens: int
    part_count: int
