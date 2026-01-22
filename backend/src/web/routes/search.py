from fastapi import APIRouter, Depends, BackgroundTasks
import time
from pathlib import Path
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Folder
from ..schemas import (
    ContextRequest,
    ContextResponse,
)
from ...config import load_config
from ...storage import make_vector_store
from ...indexer import build_index
from ...search import search as search_code
from ...prompt_builder.builder import build_prompt
router = APIRouter()

@router.post("/context", response_model=ContextResponse)
async def generate_context(
    request: ContextRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    folder = db.query(Folder).filter(Folder.id == request.folder_id).first()
    cfg = load_config(folder.path)
    collection_name = folder.name
    store = make_vector_store(cfg, collection_name=collection_name)
    if not store.exists():
        folder.status = "indexing"
        folder.error_message = None
        db.add(folder)
        db.commit()
        background_tasks.add_task(
            build_index,
            db,
            Path(folder.path),
            cfg
        )
        return ContextResponse(error="Index is being built. Please try again later.")
    else:
        start_time = time.time()
        hits = search_code(cfg, request.query, request.top_k, collection_name=collection_name)
        search_code_time = time.time() - start_time
    prompts, total_tokens = build_prompt(request.query, hits, request.language)
    build_prompt_time = time.time() - start_time
    return ContextResponse(
        prompts=prompts,
        part_count=len(prompts),
        search_code_time = search_code_time,
        build_prompt_time = build_prompt_time,
        total_tokens=total_tokens
    )