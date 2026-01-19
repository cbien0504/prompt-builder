# Adding a New Vector Store Backend

This guide explains how to add a new vector store backend to the system using the Plugin Architecture.

## Overview

The system uses a **Registry Pattern** with **auto-discovery** to support multiple vector store backends. Adding a new backend requires:

1. Creating a new implementation file
2. Implementing the `VectorStore` abstract class
3. Registering with `@VectorStoreRegistry.register()` decorator
4. Updating configuration schema (optional)

## Step-by-Step Guide

### 1. Create Implementation File

Create a new file in `src/storage/` with your backend name:

```bash
touch src/storage/pinecone.py
```

### 2. Implement VectorStore Interface

```python
"""Pinecone vector database backend."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core.models import ChunkRecord
from .base import VectorStore, VectorStoreRegistry

logger = logging.getLogger(__name__)


@VectorStoreRegistry.register("pinecone")  # Register with unique backend name
class PineconeVectorStore(VectorStore):
    """Vector storage using Pinecone."""
    
    def __init__(self, api_key: str, environment: str, index_name: str):
        """Initialize Pinecone vector store.
        
        Args:
            api_key: Pinecone API key
            environment: Pinecone environment (e.g., "us-west1-gcp")
            index_name: Name of the index
        """
        try:
            import pinecone
        except ImportError:
            raise SystemExit(
                "Pinecone not installed. Run: pip install pinecone-client"
            )
        
        self.api_key = api_key
        self.environment = environment
        self.index_name = index_name
        
        # Initialize Pinecone
        pinecone.init(api_key=api_key, environment=environment)
        self.index = pinecone.Index(index_name)
        
        logger.info(f"Initialized Pinecone index: {index_name}")
    
    # Implement all abstract methods from VectorStore
    
    def save_records(self, records: List[ChunkRecord], metadata: Dict) -> None:
        """Save records to Pinecone."""
        # Your implementation here
        pass
    
    def load_records(self, repo_filter: Optional[str] = None) -> Tuple[List[ChunkRecord], Dict]:
        """Load records from Pinecone."""
        # Your implementation here
        pass
    
    def search(
        self, 
        query_vector: List[float], 
        top_k: int, 
        repo_filter: Optional[str] = None
    ) -> List[Tuple[float, ChunkRecord]]:
        """Search using Pinecone."""
        # Your implementation here
        pass
    
    def get_metadata(self, repo_filter: Optional[str] = None) -> Optional[Dict]:
        """Get metadata from Pinecone."""
        # Your implementation here
        pass
    
    def clear(self) -> None:
        """Clear Pinecone index."""
        # Your implementation here
        pass
    
    def exists(self) -> bool:
        """Check if index has data."""
        # Your implementation here
        pass
    
    # Optional: Override lifecycle methods
    
    def connect(self) -> None:
        """Establish connection to Pinecone."""
        # Connection is established in __init__
        logger.debug(f"Connected to Pinecone index: {self.index_name}")
    
    def health_check(self) -> bool:
        """Check if Pinecone is healthy."""
        try:
            self.index.describe_index_stats()
            return True
        except Exception:
            return False
    
    # Optional: Override utility methods for better performance
    
    def count(self, repo_filter: Optional[str] = None) -> int:
        """Count records in Pinecone."""
        stats = self.index.describe_index_stats()
        return stats.total_vector_count
```

### 3. Update Configuration Schema

Add your backend configuration to `src/config/manager.py`:

```python
DEFAULT_CONFIG: Dict = {
    # ... existing config ...
    "vector_store": {
        "backend": "qdrant",  # Default backend
        
        # ... existing backends ...
        
        # Pinecone-specific configuration
        "pinecone": {
            "api_key": "${PINECONE_API_KEY}",  # From environment variable
            "environment": "us-west1-gcp",
            "index_name": None,  # Auto-generated if not set
        },
    },
}
```

### 4. Update Factory (Optional)

If your backend requires special initialization logic, update `src/storage/factory.py`:

```python
def create_vector_store(...) -> VectorStore:
    # ... existing code ...
    
    # Instantiate the vector store based on backend
    try:
        if backend == "qdrant":
            # ... existing code ...
        
        elif backend == "pinecone":
            api_key = backend_cfg.get("api_key", "")
            environment = backend_cfg.get("environment", "")
            index_name = collection_name
            return store_class(
                api_key=api_key,
                environment=environment,
                index_name=index_name
            )
        
        # ... rest of code ...
```

### 5. Add Dependencies (Optional)

If your backend requires additional packages, add them to `requirements.txt`:

```
pinecone-client>=2.0.0
```

## Testing Your Implementation

### 1. Test Registration

```python
from src.storage import get_available_backends

print(get_available_backends())
# Should include: ['chromadb', 'pinecone', 'qdrant']
```

### 2. Test Instantiation

```python
from src.storage import create_vector_store
from pathlib import Path

cfg = {
    "vector_store": {
        "backend": "pinecone",
        "pinecone": {
            "api_key": "your-api-key",
            "environment": "us-west1-gcp",
        }
    }
}

store = create_vector_store(cfg, Path("/path/to/repo"))
print(f"Created {store.BACKEND_NAME} store")
```

### 3. Test Basic Operations

```python
# Test health check
assert store.health_check() == True

# Test save/load
from src.core.models import ChunkRecord

records = [
    ChunkRecord(
        path="test.py",
        start_line=1,
        end_line=10,
        file_hash="abc123",
        chunk_hash="def456",
        text="test code",
        emb=[0.1] * 768
    )
]

metadata = {
    "repo": "/path/to/repo",
    "created_at": "2024-01-01",
}

store.save_records(records, metadata)
loaded_records, loaded_meta = store.load_records()
assert len(loaded_records) == 1
```

## Switching Between Backends

To switch from one backend to another, simply update the configuration:

```python
# Before (using Qdrant)
cfg = {
    "vector_store": {
        "backend": "qdrant",
        "qdrant": {"host": "localhost", "port": 6333}
    }
}

# After (using Pinecone)
cfg = {
    "vector_store": {
        "backend": "pinecone",
        "pinecone": {
            "api_key": "your-key",
            "environment": "us-west1-gcp"
        }
    }
}
```

No code changes required! The factory will automatically use the correct implementation.

## Example: ChromaDB Implementation

See `src/storage/chromadb.py` for a complete example implementation.

## Best Practices

1. **Error Handling**: Provide clear error messages when dependencies are missing
2. **Logging**: Use `logger.info()` for important operations, `logger.debug()` for details
3. **Performance**: Override utility methods (`count`, `delete_by_filter`) for better performance
4. **Documentation**: Add docstrings explaining backend-specific behavior
5. **Testing**: Test with real backend service before committing

## Troubleshooting

### Backend Not Found

```
KeyError: Vector store backend 'mybackend' not found. Available backends: chromadb, qdrant
```

**Solution**: Make sure your file is in `src/storage/` and uses the `@VectorStoreRegistry.register()` decorator.

### Import Errors

```
SystemExit: MyBackend not installed. Run: pip install mybackend
```

**Solution**: Install the required dependencies or add them to `requirements.txt`.

### Connection Errors

```
SystemExit: Failed to initialize mybackend vector store.
```

**Solution**: Check your configuration and ensure the backend service is running.
