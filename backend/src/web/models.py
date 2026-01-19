"""SQLAlchemy models."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Folder(Base):
    """Folder model for tracking indexed directories."""
    
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String(1024), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, index=True)  # pending, indexing, indexed, error
    repo_count = Column(Integer, default=0)  # Number of repositories in this subproject
    total_files = Column(Integer, default=0)
    indexed_files = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    last_indexed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    error_message = Column(Text)

    # Relationships
    index_stats = relationship("IndexStat", back_populates="folder", cascade="all, delete-orphan")


class IndexStat(Base):
    """Index statistics for tracking indexed files."""
    
    __tablename__ = "index_stats"

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(1024), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    chunks_count = Column(Integer, nullable=False)
    indexed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    folder = relationship("Folder", back_populates="index_stats")
