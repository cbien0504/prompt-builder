from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Literal


class FolderBase(BaseModel):
    path: str
    name: str

class FolderCreate(BaseModel):
    path: str

class FolderResponse(BaseModel):
    id: int
    path: str
    name: str
    status: str
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
    incremental: bool = True


class SearchRequest(BaseModel):
    query: str
    folder_id: int
    top_k: int = 10


class SearchResult(BaseModel):
    folder_id: int
    folder_name: str
    file_path: str
    start_line: int
    end_line: int
    score: float
    text: str


class SearchResponse(BaseModel):
    results: List[SearchResult]


class ContextRequest(SearchRequest):
    language: Literal["eng", "vie"] = "vie"

class ContextResponse(BaseModel):
    prompts: Optional[List[str]] = None
    total_tokens: Optional[int] = None
    part_count: Optional[int] = None
    error: Optional[str] = None
    search_code_time: Optional[float] = None
    build_prompt_time: Optional[float] = None


class AnswerRequest(BaseModel):
    query: Optional[str] = None
    folder_id: int
    top_k: int = 10
    include_prompts: bool = False

class AnswerResponse(BaseModel):
    answer: Optional[str] = None
    time_taken: float
    usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None