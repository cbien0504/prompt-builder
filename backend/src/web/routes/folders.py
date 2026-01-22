from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import os
import shutil
from functools import lru_cache
from ...config import load_config
from ...storage import create_vector_store
from qdrant_client import QdrantClient
import hashlib
from ..database import get_db
from ..models import Folder
from ..schemas import FolderCreate, FolderResponse
from ...config import load_config
from ...indexer import build_index

router = APIRouter(prefix="/folders")

PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/host_c/Project")


@router.get("", response_model=List[FolderResponse])
async def list_folders(db: Session = Depends(get_db)):
    project_root = Path(PROJECT_ROOT)

    fs_folders = {
        p.name for p in project_root.iterdir() if p.is_dir()
    }

    db_folders = db.query(Folder).all()
    db_folder_names = {f.name for f in db_folders}

    fs_only = fs_folders - db_folder_names
    for folder_name in fs_only:
        shutil.rmtree(project_root / folder_name)

    db_only = db_folder_names - fs_folders
    if db_only:
        db.query(Folder).filter(Folder.name.in_(db_only)).delete(
            synchronize_session=False
        )
        db.commit()

    return db.query(Folder).all()

@router.post("/import")
async def import_project(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    project_name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    print("files", files)
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if not project_name:
        first_file = files[0]
        if hasattr(first_file, 'filename') and first_file.filename:
            relative_path = getattr(first_file, 'webkitRelativePath', None) or first_file.filename
            if relative_path:
                parts = relative_path.replace('\\', '/').split('/')
                if parts:
                    project_name = parts[0]
        
        if not project_name:
            project_name = f"project_{int(os.urandom(4).hex(), 16)}"
    
    project_name = "".join(c for c in project_name if c.isalnum() or c in ('-', '_'))
    if not project_name:
        project_name = f"project_{int(os.urandom(4).hex(), 16)}"
    
    project_root = Path(PROJECT_ROOT)
    project_root.mkdir(parents=True, exist_ok=True)
    project_path = project_root / project_name
    
    if project_path.exists():
        raise HTTPException(status_code=400, detail=f"Project '{project_name}' already exists")
    
    project_path.mkdir(parents=True, exist_ok=True)
    for file in files:
        if not file.filename:
            continue
        relative_path = getattr(file, "webkitRelativePath", None) or file.filename
        relative_path = relative_path.replace("\\", "/")
        if relative_path.startswith(project_name + "/"):
            relative_path = relative_path[len(project_name) + 1 :]
        if not relative_path or relative_path == "/" or relative_path == project_name:
            continue
        target_path = project_path / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("wb") as f:
            content = await file.read()
            f.write(content)

    folder = Folder(
        path=str(project_path),
        name=project_name,
        status="indexing",
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)

    cfg = load_config(project_path)
    background_tasks.add_task(
        build_index,
        db,
        Path(project_path),
        cfg,
    )
    return {
        "message": f"Project '{project_name}' imported successfully",
        "folder_id": folder.id,
        "project_name": project_name,
        "path": str(project_path),
    }


@router.get("/{folder_id:int}", response_model=FolderResponse)
async def get_folder(folder_id: int, db: Session = Depends(get_db)):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder

@router.get("/{folder_id:int}/file")
async def get_file_content(
    folder_id: int, 
    path: str,
    if_none_match: Optional[str] = Header(None)
):
    def get_file_hash(file_path: Path) -> str:
        stat = file_path.stat()
        return hashlib.md5(f"{stat.st_mtime}:{stat.st_size}".encode()).hexdigest()

    base = Path(PROJECT_ROOT).resolve()
    target = (base / path).resolve()
    try:
        target.relative_to(base)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    current_etag = get_file_hash(target)
    
    if if_none_match and if_none_match == current_etag:
        return JSONResponse(
            status_code=304,
            headers={"ETag": current_etag},
            content={
                "path": path,
                "content": target.read_text(encoding="utf-8"),
                "etag": current_etag
            }
        )
    
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = target.read_text(encoding="latin-1")
    
    return JSONResponse(
        content={
            "path": path,
            "content": content,
            "etag": current_etag
        },
        headers={"ETag": current_etag}
    )


@router.get("/{folder_id:int}/tree")
async def get_folder_tree(folder_id: int, db: Session = Depends(get_db)):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    folder_path = Path(folder.path)
    if not folder_path.exists() or not folder_path.is_dir():
        raise HTTPException(status_code=404, detail="Folder path does not exist")
    
    def build_tree(path: Path, base_path: Path) -> dict:
        result = {
            "name": path.name,
            "path": str(path.relative_to(base_path)) if path != base_path else "",
            "type": "directory" if path.is_dir() else "file",
            "children": []
        }
        
        if path.is_dir():
            try:
                items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
                for item in items:
                    if item.name.startswith('.'):
                        continue
                    result["children"].append(build_tree(item, base_path))
            except PermissionError:
                pass
        
        return result
    
    tree = build_tree(folder_path, folder_path)
    return tree


@router.delete("/{folder_id:int}")
async def delete_folder(folder_id: int, db: Session = Depends(get_db)):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    folder_path = Path(folder.path)
    db.delete(folder)
    db.commit()

    try:
        if folder_path.exists():
            shutil.rmtree(folder_path, ignore_errors=True)
    except Exception as e:
        print(f"Warning: failed to remove folder from disk: {e}")

    try:
        cfg = load_config(folder_path)
        collection_name = folder_path.name
        store = create_vector_store(cfg, folder_path, collection_name=collection_name)
        if hasattr(store, "client") and hasattr(store.client, "delete_collection"):
            store.client.delete_collection(collection_name=collection_name)
        else:
            store.clear()
    except Exception as e:
        print(f"Warning: failed to delete Qdrant collection: {e}")

    return {"success": True, "message": "Folder and collection deleted"}
