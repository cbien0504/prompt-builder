"""Indexing routes with SSE support."""

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
import asyncio
from datetime import datetime
from pathlib import Path

from ...config import load_config
from ...indexing import build_index
from ...storage import make_vector_store

from ..database import get_db
from ..models import Folder, IndexStat
from ..schemas import IndexRequest

router = APIRouter(prefix="/folders")

# Global dict to track indexing progress
indexing_progress = {}


def index_folder_task(folder_id: int, incremental: bool = True):
    """Background task to index a folder directly."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import os
    
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/prompt_builder"
    )
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        if not folder:
            return
        
        folder_path = Path(folder.path)
        print(f"folder_path: {folder_path}")
        if not folder_path.exists():
            folder.status = "error"
            folder.error_message = "Folder path does not exist"
            db.commit()
            return
        
        if not folder_path.is_dir():
            folder.status = "error"
            folder.error_message = "Path is not a directory"
            db.commit()
            return
        
        folder.status = "indexing"
        db.commit()
        
        cfg = load_config(folder_path)
        
        indexing_progress[folder_id] = {
            "current": 0,
            "total": 1,
            "status": "indexing",
            "current_repo": folder.name
        }
        
        try:
            # Determine collection name for this folder
            from ...utils.file_utils import get_sub_project_name
            import re
            
            # Use folder name for collection
            folder_name = get_sub_project_name(folder_path)
            clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', folder_name)
            collection_name = clean_name
            
            print(f"Indexing folder {folder.name} (path: {folder_path}) into collection: {collection_name}")
            
            # Index the folder directly
            build_index(folder_path, cfg, incremental=incremental, collection_name=collection_name)
            
            # Get vector store to count chunks
            store = make_vector_store(cfg, folder_path, collection_name=collection_name)
            records, metadata = store.load_records()
            print(f"Loaded {len(records)} total records from folder {folder.name}")
            
            # Update folder stats
            folder.status = "indexed"
            folder.total_chunks = len(records)
            folder.last_indexed_at = datetime.utcnow()
            folder.error_message = None
            
            # Update index stats
            file_stats = {}
            for record in records:
                if record.path not in file_stats:
                    file_stats[record.path] = {
                        "hash": record.file_hash,
                        "chunks": 0
                    }
                file_stats[record.path]["chunks"] += 1
            
            folder.total_files = len(file_stats)
            folder.indexed_files = len(file_stats)
            
            # Save index stats
            for file_path, stats in file_stats.items():
                # Check if exists
                existing = db.query(IndexStat).filter(
                    IndexStat.folder_id == folder_id,
                    IndexStat.file_path == file_path
                ).first()
                
                if existing:
                    existing.file_hash = stats["hash"]
                    existing.chunks_count = stats["chunks"]
                    existing.indexed_at = datetime.utcnow()
                else:
                    stat = IndexStat(
                        folder_id=folder_id,
                        file_path=file_path,
                        file_hash=stats["hash"],
                        chunks_count=stats["chunks"]
                    )
                    db.add(stat)
            
            db.commit()
            print(f"Folder {folder_id} ({folder.name}) indexed successfully with {len(records)} chunks")
            
            indexing_progress[folder_id]["status"] = "indexed"
            indexing_progress[folder_id]["current"] = 1
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error indexing folder {folder_id}: {e}")
            folder.status = "error"
            folder.error_message = str(e)
            db.commit()
            indexing_progress[folder_id]["status"] = "error"
            indexing_progress[folder_id]["error"] = str(e)
            
    finally:
        db.close()


@router.post("/{folder_id}/index")
async def start_indexing(
    folder_id: int,
    request: IndexRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start indexing all repositories in a subproject."""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if folder.status == "indexing":
        raise HTTPException(status_code=400, detail="Folder is already being indexed")
    
    # Update status immediately
    folder.status = "indexing"
    folder.error_message = None
    db.commit()
    
    # Start background task
    print(f"Starting background indexing task for folder {folder_id} ({folder.name})")
    background_tasks.add_task(index_folder_task, folder_id, request.incremental)
    
    return {
        "message": f"Indexing started for folder '{folder.name}'",
        "folder_id": folder_id
    }


@router.get("/{folder_id}/index/progress")
async def index_progress(folder_id: int, db: Session = Depends(get_db)):
    """SSE endpoint for real-time indexing progress."""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    async def event_generator():
        """Generate SSE events for progress updates."""
        while True:
            # Refresh folder status from DB
            db.refresh(folder)
            
            progress = indexing_progress.get(folder_id, {})
            
            yield {
                "event": "progress",
                "data": {
                    "folder_id": folder_id,
                    "status": folder.status,
                    "indexed_files": folder.indexed_files,
                    "total_files": folder.total_files,
                    "total_chunks": folder.total_chunks,
                    "current": progress.get("current", 0),
                    "total": progress.get("total", 1),
                    "current_repo": progress.get("current_repo", folder.name),
                    "error": folder.error_message
                }
            }
            
            if folder.status in ["indexed", "error"]:
                # Clean up progress tracking
                if folder_id in indexing_progress:
                    del indexing_progress[folder_id]
                break
            
            await asyncio.sleep(1)
    
    return EventSourceResponse(event_generator())


@router.post("/{folder_id}/index/cancel")
async def cancel_indexing(folder_id: int, db: Session = Depends(get_db)):
    """Cancel ongoing indexing."""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if folder.status != "indexing":
        raise HTTPException(status_code=400, detail="Folder is not being indexed")
    
    # TODO: Implement actual cancellation logic
    folder.status = "pending"
    folder.error_message = "Cancelled by user"
    db.commit()
    
    # Clean up progress
    if folder_id in indexing_progress:
        del indexing_progress[folder_id]
    
    return {"success": True, "message": "Indexing cancelled"}

