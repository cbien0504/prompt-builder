"""Main FastAPI application."""

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import os

from .database import engine, Base
from .routes import folders, indexing, search

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

# Create API router
api_router = APIRouter(prefix="/api")

# Include routers under /api
api_router.include_router(folders.router)
api_router.include_router(indexing.router)
api_router.include_router(search.router)

# Include API router in app
app.include_router(api_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
