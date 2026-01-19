# Prompt Builder

**Công cụ quản lý và index codebase theo subproject với tính năng semantic search và prompt generation cho LLM.**

## ✨ Tính năng

- 📂 **Subproject-Level Indexing**: Quản lý theo subproject, tự động index tất cả repositories liên quan
- 🔍 **Semantic Search**: Tìm kiếm code bằng ngôn ngữ tự nhiên với Jina Embeddings v2
- 🌳 **AST-Based Chunking**: Phân tích code theo cấu trúc AST thay vì line-based
- 🎯 **Smart Context**: Tự động thu thập context từ nhiều repos trong cùng subproject
- 🤖 **LLM Prompt Builder**: Tạo prompt với token management và auto-splitting
- ⚡ **Incremental Indexing**: Chỉ index files thay đổi, tiết kiệm thời gian
- 🐳 **Fully Dockerized**: Deploy dễ dàng với Docker Compose

## 🚀 Quick Start

### Yêu cầu

- **Docker** và **Docker Compose**
- Thư mục code cần index (cấu trúc: `/project/subproject/repo`)

### Khởi động

```bash
# Clone repository
git clone <repo-url>
cd cursorlite

# Start all services
docker compose up -d --build

# Truy cập ứng dụng
open http://localhost:3000

# Truy cập Qdrant
open http://localhost:6333/dashboard
```

## 📁 Cấu trúc Project

### Cấu trúc Thư mục Code

```
/project/
  ├── frontend_projects/    # Subproject 1
  │   ├── react-app/        # Repo 1
  │   └── vue-app/          # Repo 2
  ├── backend_services/     # Subproject 2
  │   ├── api-service/
  │   └── auth-service/
  └── mobile_apps/          # Subproject 3
      ├── android-app/
      └── ios-app/
```

**Lưu ý quan trọng:**
- Hệ thống track theo **subproject** (ví dụ: `frontend_projects`)
- Khi index một subproject → index **tất cả repos** bên trong
- Mỗi subproject có **Qdrant collection riêng** (ví dụ: `cursorlite_frontend_projects`)
- Search và prompt sẽ tìm trong **tất cả repos** của subproject

### Cấu trúc Code

```
cursorlite/
├── backend/
│   ├── src/
│   │   ├── core/           # Chunking, Embeddings, Models
│   │   ├── indexing/       # Indexing Pipeline
│   │   ├── search/         # Search Logic
│   │   ├── prompt/         # Prompt Builder
│   │   ├── storage/        # Qdrant Vector Store
│   │   ├── web/            # FastAPI Routes
│   │   └── utils/          # Utilities
│   ├── alembic/            # Database Migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # React + Vite
├── docker-compose.yml
└── project/               # Mount point cho code cần index
```

## 🎯 Hướng dẫn Sử dụng

### 1. Discover Subprojects

```bash
# Tự động phát hiện subprojects
POST /folders/discover

# Response
{
  "added": ["/project/frontend_projects"],
  "repo_count": 2,
  "total_found": 3
}
```

### 2. Index Subproject

```bash
# Index tất cả repos trong subproject
POST /folders/{id}/index

# Response  
{
  "message": "Indexing started for subproject 'frontend_projects' with 2 repositories",
  "folder_id": 1,
  "repo_count": 2
}
```

**Quá trình indexing:**
1. Quét tất cả files trong mỗi repo
2. AST chunking cho code files(Python, JS, PHP, etc.)
3. Line-based chunking cho config files
4. Generate embeddings với Jina v2
5. Store vào Qdrant collection `cursorlite_{subproject_name}`

### 3. Search Code

```bash
# Tìm kiếm trong subproject
POST /search
{
  "query": "authentication logic",
  "folder_ids": [1],
  "top_k": 10
}
```

**Kết quả:**
- Tìm trong tất cả repos của subproject
- Ranked by semantic similarity
- Hiển thị file path, line numbers, và code snippet

### 4. Generate LLM Prompt

```bash
# Tạo prompt với context
POST /context
{
  "task": "Explain how authentication works",
  "folder_ids": [1],
  "top_k": 10
}

# Response
{
  "prompts": ["<part 1>", "<part 2>"],
  "total_tokens": 15000,
  "part_count": 2
}
```

**Features:**
- Tự động thu thập relevant code từ nhiều repos
- Token counting và management
- Auto-split nếu vượt quá 32k tokens
- Multi-part prompts cho large context

## 🛠️ Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** + **PostgreSQL** - Metadata storage
- **Qdrant** - Vector database
- **Sentence Transformers** - Jina Embeddings v2 (768d)
- **Tree-sitter** - AST parsing
- **Tiktoken** - Token counting

### Frontend
- **React** + **Vite** - UI framework
- **CSS Modules** - Styling

### Infrastructure
- **Docker Compose** - Container orchestration
- **Alembic** - Database migrations

## ⚙️ Configuration

### Environment Variables

```yaml
# Backend
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/prompt_builder
QDRANT_HOST=qdrant
QDRANT_PORT=6333
PROJECT_ROOT=/project

# Indexing
MAX_FILE_SIZE_KB=512
CHUNK_MAX_LINES=120
CHUNK_OVERLAP_LINES=20
```

### Docker Volumes

```yaml
volumes:
  - ./backend:/app              # Hot reload for development
  - ./project:/project          # Your code to index
  - postgres_data:/var/lib/postgresql/data
  - qdrant_storage:/qdrant/storage
```

## 🔧 Development

### Local Development

```bash
# Start with hot reload
docker compose up

# Run migrations
docker compose exec backend alembic upgrade head

# View logs
docker compose logs -f backend
```

### Database Migrations

```bash
# Create new migration
docker compose exec backend alembic revision -m "description"

# Apply migrations
docker compose exec backend alembic upgrade head

# Rollback
docker compose exec backend alembic downgrade -1
```

### Testing

```bash
# Health check
curl http://localhost:8000/health

# Discover subprojects
curl -X POST http://localhost:8000/folders/discover

# List folders
curl http://localhost:8000/folders
```

## 📊 Architecture

### Indexing Flow

```mermaid
graph TD
    A[Discover Subprojects] --> B[Get All Repos]
    B --> C[For Each Repo]
    C --> D[Scan Files]
    D --> E[AST Chunking]
    E --> F[Generate Embeddings]
    F --> G[Store in Qdrant]
    G --> H[Update Metadata]
```

### Search Flow

```mermaid
graph TD
    A[User Query] --> B[Generate Query Embedding]
    B --> C[Search Qdrant Collection]
    C --> D[Get Top-K Similar Chunks]
    D --> E[Rank by Score]
    E --> F[Return Results]
```

## 🐛 Troubleshooting

### AST Chunking Errors

Nếu thấy lỗi `__init__() takes exactly 1 argument (2 given)`:
- ✅ Đã fix bằng cách chuyển sang `tree-sitter-language-pack`
- Rebuild: `docker compose up --build`

### Qdrant Connection Issues

```bash
# Check Qdrant health
curl http://localhost:6333/health

# View collections
curl http://localhost:6333/collections
```

### Database Issues

```bash
# Reset database
docker compose down -v
docker compose up -d
docker compose exec backend alembic upgrade head
```

## 📝 API Documentation

Truy cập: http://localhost:8000/docs

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

- **Jina AI** - Jina Embeddings v2
- **Qdrant** - Vector Database
- **Tree-sitter** - Code Parsing
- **FastAPI** - Web Framework