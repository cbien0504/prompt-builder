"""Search routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pathlib import Path

from ...config import load_config
from ...storage import make_vector_store
from ...indexing import build_index
from datetime import datetime
from ...search import search as search_code
from ...prompt import build_prompt

from ..database import get_db
from ..models import Folder
from ..schemas import SearchRequest, SearchResponse, SearchResult, ContextRequest, ContextResponse

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, db: Session = Depends(get_db)):
    folder = db.query(Folder).filter(Folder.id == request.folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    folder_path = Path(folder.path)
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail="Folder not found")
    
    cfg = load_config(folder_path)
    collection_name = folder_path.name.replace("project/", "")
    
    store = make_vector_store(cfg, collection_name=collection_name)
    
    if not store.exists():
        print(f"Collection '{collection_name}' needs indexing, starting auto-index...")
        folder.status = "indexing"
        folder.error_message = None
        db.commit()
        
        try:
            build_index(folder_path, cfg, incremental=False, collection_name=collection_name)
            
            records, metadata = store.load_records()
            
            folder.status = "indexed"
            folder.total_chunks = len(records)
            folder.last_indexed_at = datetime.utcnow()
            folder.error_message = None
            
            file_stats = {}
            for record in records:
                if record.path not in file_stats:
                    file_stats[record.path] = {"chunks": 0}
                file_stats[record.path]["chunks"] += 1
            
            folder.total_files = len(file_stats)
            folder.indexed_files = len(file_stats)
            db.commit()
            print(f"Auto-indexed folder {folder.id} ({folder.name}) with {len(records)} chunks")
        except Exception as index_error:
            folder.status = "error"
            folder.error_message = str(index_error)
            db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to auto-index: {index_error}")
    
    hits = search_code(folder_path, cfg, request.query, request.top_k, collection_name=collection_name)
    
    results = []
    for score, record in hits:
        result = SearchResult(
            folder_id=request.folder_id,
            folder_name=folder.name,
            file_path=record.path,
            start_line=record.start_line,
            end_line=record.end_line,
            score=score,
            text=record.text
        )
        results.append(result)
    
    return SearchResponse(results=results)

@router.post("/context", response_model=ContextResponse)
async def generate_context(request: ContextRequest, db: Session = Depends(get_db)):
    """Generate LLM context from search results."""
    # Get folders to search
    if request.folder_ids:
        folders = db.query(Folder).filter(
            Folder.id.in_(request.folder_ids),
            Folder.status == "indexed"
        ).all()
    else:
        folders = db.query(Folder).filter(Folder.status == "indexed").all()
    
    if not folders:
        return ContextResponse(prompt="No indexed folders found")
    
    all_hits = []
    
    all_hits = []
    
    # helper for grouping
    from ...utils.file_utils import get_sub_project_name
    
    # 1. Group folders by sub-project
    sub_projects = {}
    
    for folder in folders:
        folder_path = Path(folder.path)
        if not folder_path.exists():
            continue
        
        sp = get_sub_project_name(folder_path)
        if sp not in sub_projects:
            sub_projects[sp] = []
        sub_projects[sp].append(folder)
        
    # 2. Search each sub-project once
    for sp, sp_folders in sub_projects.items():
        if not sp_folders:
            continue
        
        representative_folder = sp_folders[0]
        folder_path = Path(representative_folder.path)
        
        try:
            cfg = load_config(folder_path)
            # Generate collection name same as indexing
            from ...utils.file_utils import get_sub_project_name
            import re
            folder_name = get_sub_project_name(folder_path)
            clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', folder_name)
            collection_name = clean_name
            hits = search_code(folder_path, cfg, request.task, request.top_k, collection_name=collection_name)
            all_hits.extend(hits)
        except Exception as e:
            print(f"Error searching subproject {sp}: {e}")
            continue
    
    # Sort by score and limit
    all_hits.sort(key=lambda x: x[0], reverse=True)
    all_hits = all_hits[:request.top_k]
    
    # Build prompt
    prompts, total_tokens = build_prompt(request.task, all_hits)
    
    return ContextResponse(
        prompts=prompts,
        total_tokens=total_tokens,
        part_count=len(prompts)
    )

