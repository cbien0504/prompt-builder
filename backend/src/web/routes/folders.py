"""Folder management routes."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import os
import shutil

from ..database import get_db
from ..models import Folder
from ..schemas import FolderCreate, FolderResponse

router = APIRouter(prefix="/folders")

# Project root directory (mounted in container)
PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/host_c/Project")


def is_repo(path: Path) -> bool:
    """Check if a directory is a repository."""
    if not path.is_dir():
        return False
    return (path / ".git").exists() or any(path.glob("*.py")) or any(path.glob("*.js"))


def discover_subprojects(base_path: Path) -> List[Path]:
    """Discover all subprojects in the project directory.
    
    Returns list of paths that are either:
    1. A directory containing repositories (Project/Group/Repo)
    2. A repository directly under root (Project/Repo)
    """
    subprojects = []
    
    if not base_path.exists():
        return subprojects
    
    # Scan project/* based on structure
    for path in base_path.iterdir():
        if not path.is_dir():
            continue
            
        # Case 1: The path itself is a repo (Flat structure: Project/Repo)
        if is_repo(path):
            subprojects.append(path)
            continue
            
        # Case 2: The path is a group containing repos (Nested: Project/Group/Repo)
        has_child_repos = False
        for child in path.iterdir():
            if is_repo(child):
                has_child_repos = True
                break
        
        if has_child_repos:
            subprojects.append(path)
    
    return subprojects


def get_repos_in_subproject(subproject_path: Path) -> List[Path]:
    """Get all repositories within a subproject.
    
    If subproject_path is itself a repo, returns [subproject_path].
    Otherwise returns list of child repositories.
    """
    # Case 1: The subproject path itself is a repo
    if (subproject_path / ".git").exists():
        return [subproject_path]
        
    # Case 2: Scan for child repos
    repos = []
    for repo_dir in subproject_path.iterdir():
        if is_repo(repo_dir):
            repos.append(repo_dir)
            
    # Fallback: if no children found but has code, treat as repo (for non-git folders)
    if not repos and is_repo(subproject_path):
        return [subproject_path]
        
    return repos


@router.get("", response_model=List[FolderResponse])
async def list_folders(db: Session = Depends(get_db)):
    """List all tracked folders."""
    folders = db.query(Folder).all()
    return folders


@router.post("/import")
async def import_project(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    project_name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Import a project by uploading files/folders. Creates directory in /project and auto-indexes."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Determine project name
    if not project_name:
        # Try to get project name from first file's path
        first_file = files[0]
        if hasattr(first_file, 'filename') and first_file.filename:
            # Extract project name from webkitRelativePath (e.g., "myproject/src/file.py" -> "myproject")
            relative_path = getattr(first_file, 'webkitRelativePath', None) or first_file.filename
            if relative_path:
                parts = relative_path.replace('\\', '/').split('/')
                if parts:
                    project_name = parts[0]
        
        if not project_name:
            project_name = f"project_{int(os.urandom(4).hex(), 16)}"
    
    # Sanitize project name
    project_name = "".join(c for c in project_name if c.isalnum() or c in ('-', '_'))
    if not project_name:
        project_name = f"project_{int(os.urandom(4).hex(), 16)}"
    
    # Create project directory
    project_root = Path(PROJECT_ROOT)
    project_root.mkdir(parents=True, exist_ok=True)
    project_path = project_root / project_name
    
    if project_path.exists():
        raise HTTPException(status_code=400, detail=f"Project '{project_name}' already exists")
    
    project_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save all files maintaining directory structure
        for file in files:
            if not file.filename:
                continue
            
            # Get relative path from webkitRelativePath or filename
            relative_path = getattr(file, 'webkitRelativePath', None) or file.filename
            # Normalize path separators
            relative_path = relative_path.replace('\\', '/')
            
            # Remove project name prefix if present (webkitRelativePath includes it)
            if relative_path.startswith(project_name + '/'):
                relative_path = relative_path[len(project_name) + 1:]
            
            # Skip if empty or just project name
            if not relative_path or relative_path == '/' or relative_path == project_name:
                continue
            
            # Create target file path
            target_path = project_path / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with target_path.open('wb') as f:
                content = await file.read()
                f.write(content)
        
        # Create folder record (no need to count repos, we index the folder directly)
        folder = Folder(
            path=str(project_path),
            name=project_name,
            status="pending",
            repo_count=0
        )
        db.add(folder)
        db.commit()
        db.refresh(folder)
        
        # Auto-index the imported project
        from .indexing import index_folder_task
        background_tasks.add_task(index_folder_task, folder.id, incremental=False)
        
        return {
            "message": f"Project '{project_name}' imported successfully",
            "folder_id": folder.id,
            "project_name": project_name,
            "path": str(project_path),
            "repo_count": len(repos)
        }
        
    except Exception as e:
        # Cleanup on error
        if project_path.exists():
            shutil.rmtree(project_path)
        raise HTTPException(status_code=500, detail=f"Failed to import project: {str(e)}")


@router.post("/discover")
async def discover_folders(db: Session = Depends(get_db)):
    """Auto-discover and add all subprojects in project directory."""
    project_root = Path(PROJECT_ROOT)
    
    if not project_root.exists():
        raise HTTPException(
            status_code=400, 
            detail=f"Project root does not exist: {PROJECT_ROOT}. Please create it or set PROJECT_ROOT env var."
        )
    
    subprojects = discover_subprojects(project_root)
    
    added = []
    skipped = []
    
    for subproject_path in subprojects:
        # Check if already exists
        existing = db.query(Folder).filter(Folder.path == str(subproject_path)).first()
        if existing:
            skipped.append(str(subproject_path))
            continue
        
        # Count repos in this subproject
        repos = get_repos_in_subproject(subproject_path)
        
        # Add new subproject
        folder = Folder(
            path=str(subproject_path),
            name=subproject_path.name,
            status="pending",
            repo_count=len(repos)
        )
        db.add(folder)
        added.append(str(subproject_path))
    
    db.commit()
    
    return {
        "added": added,
        "skipped": skipped,
        "total_found": len(subprojects)
    }


@router.post("", response_model=FolderResponse)
async def add_folder(request: FolderCreate, db: Session = Depends(get_db)):
    """Add a new folder to track (manual)."""
    # Convert Windows path to container path if needed
    folder_path_str = request.path
    
    # If path starts with C:\, convert to /host_c/
    if folder_path_str.startswith('C:\\') or folder_path_str.startswith('c:\\'):
        container_path = '/host_c/' + folder_path_str[3:].replace('\\', '/')
    elif folder_path_str.startswith('C:/') or folder_path_str.startswith('c:/'):
        container_path = '/host_c/' + folder_path_str[3:]
    else:
        container_path = folder_path_str
    
    # Validate path exists in container
    folder_path = Path(container_path)
    if not folder_path.exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {request.path}")
    
    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    # Check if already exists (using original Windows path)
    existing = db.query(Folder).filter(Folder.path == container_path).first()
    if existing:
        raise HTTPException(status_code=400, detail="Folder already tracked")
    
    # Create folder with container path
    folder = Folder(
        path=container_path,
        name=folder_path.name,
        status="pending"
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    
    return folder


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(folder_id: int, db: Session = Depends(get_db)):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@router.get("/{folder_id}/tree")
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


@router.delete("/{folder_id}")
async def delete_folder(folder_id: int, db: Session = Depends(get_db)):
    """Delete a folder and its associated vector store collection."""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Delete vector store collection
    try:
        from ...config.manager import load_config
        from ...storage.factory import create_vector_store
        from ...utils.file_utils import get_sub_project_name
        import re
        
        # Load config
        folder_path = Path(folder.path)
        cfg = load_config(folder_path)
        
        # Generate collection name from folder path
        sub_project = get_sub_project_name(folder_path)
        clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', sub_project)
        collection_name = clean_name
        
        try:
            store = create_vector_store(cfg)
            if hasattr(store, 'client') and hasattr(store.client, 'delete_collection'):
                store.client.delete_collection(collection_name=collection_name)
                print(f"Successfully deleted collection: {collection_name}")
            else:
                store.clear()
                print(f"Successfully cleared collection: {collection_name}")
        except Exception as e:
            # Log error but don't fail the deletion
            print(f"Warning: Failed to delete collection {collection_name}: {e}")
    except Exception as e:
        # Log error but don't fail the deletion
        print(f"Warning: Error during vector store cleanup: {e}")
    
    # Delete folder from database
    db.delete(folder)
    db.commit()
    
    return {"success": True, "message": "Folder and collection deleted"}
