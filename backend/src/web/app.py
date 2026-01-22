"""Main FastAPI application."""

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base, SessionLocal
from .models import Folder
from .routes import folders, search

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CursorLite Backend")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")

api_router.include_router(folders.router)
api_router.include_router(search.router)

app.include_router(api_router)

_auto_reindex_task: asyncio.Task | None = None


def _latest_mtime(folder_path: Path) -> float:
    """Get latest modification time inside folder (skips hidden)."""
    try:
        latest = folder_path.stat().st_mtime
    except FileNotFoundError:
        return 0

    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if fname.startswith("."):
                continue
            try:
                mtime = Path(root, fname).stat().st_mtime
                if mtime > latest:
                    latest = mtime
            except FileNotFoundError:
                continue
    return latest


# async def _auto_reindex_loop():
#     while True:
#         db = SessionLocal()
#         try:
#             folders = db.query(Folder).all()
#             loop = asyncio.get_running_loop()
#             for folder in folders:
#                 if folder.status == "indexing":
#                     continue

#                 folder_path = Path(folder.path)
#                 if not folder_path.exists():
#                     folder.status = "error"
#                     folder.error_message = "Folder path does not exist"
#                     db.commit()
#                     continue

#                 latest_mtime = _latest_mtime(folder_path)
#                 last_index_ts = (
#                     folder.last_indexed_at.timestamp() if folder.last_indexed_at else 0
#                 )

#                 needs_reindex = False
#                 if folder.status == "error":
#                     needs_reindex = True
#                 elif folder.total_chunks == 0:
#                     needs_reindex = True
#                 elif latest_mtime > last_index_ts:
#                     needs_reindex = True

#                 if needs_reindex:
#                     folder.status = "pending"
#                     folder.error_message = None
#                     db.commit()
#         except Exception as e:
#             print(f"[AutoReindex] Error in loop: {e}")
#         finally:
#             db.close()

#         await asyncio.sleep(5)


# @app.on_event("startup")
# async def _start_auto_reindex():
#     global _auto_reindex_task
#     if _auto_reindex_task is None:
#         _auto_reindex_task = asyncio.create_task(_auto_reindex_loop())


# @app.on_event("shutdown")
# async def _stop_auto_reindex():
#     global _auto_reindex_task
#     if _auto_reindex_task:
#         _auto_reindex_task.cancel()
#         try:
#             await _auto_reindex_task
#         except asyncio.CancelledError:
#             pass
#         _auto_reindex_task = None
