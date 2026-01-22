import ignore from 'ignore'

const API_BASE = '/api'

export const api = {
    async getFolders() {
        const res = await fetch(`${API_BASE}/folders`)
        if (!res.ok) throw new Error('Failed to fetch folders')
        return res.json()
    },

    async importProject(files: FileList) {
        const DEFAULT_INCLUDE = [
            "*.py", "*.js", "*.ts", "*.tsx", "*.jsx",
            "*.go", "*.java", "*.kt", "*.cs",
            "*.rb", "*.php", "*.rs",
            "*.c", "*.h", "*.cpp", "*.hpp",
            "*.swift",
            "*.txt", "*.yaml", "*.yml", "*.json",
            "*.md", "*.mdx",
            "*.html", "*.css", "*.scss", "*.sass",
            "*.vue", "*.svelte",
        ]

        const DEFAULT_EXCLUDE = [
            // Version Control
            ".git",
            ".svn",
            ".hg",
            
            // Dependencies
            "node_modules",
            "vendor",
            "bower_components",
            
            // Build outputs
            "dist",
            "build",
            "out",
            "target",
            "bin",
            "obj",
            ".next",
            ".nuxt",
            ".output",
            
            // Python
            ".venv",
            "venv",
            "env",
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".Python",
            "pip-log.txt",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "*.egg-info",
            
            // IDEs & Editors
            ".idea",
            ".vscode",
            ".vs",
            "*.swp",
            "*.swo",
            "*~",
            ".DS_Store",
            "Thumbs.db",
            ".cursorlite",
            
            // Environment & Config
            ".env",
            ".env.*",
            
            // Logs
            "*.log",
            "logs",
            "npm-debug.log*",
            "yarn-debug.log*",
            "yarn-error.log*",
            
            // Testing
            "coverage",
            ".nyc_output",
            "*.cover",
            ".coverage",
            "htmlcov",
            
            // Cache
            ".cache",
            ".parcel-cache",
            ".eslintcache",
            ".stylelintcache",
            
            // Temporary
            "tmp",
            "temp",
            "*.tmp",
            
            // Package managers lock files
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "Cargo.lock",
            "Gemfile.lock",
            "composer.lock",
            "poetry.lock",
            
            // Mobile
            "*.xcworkspace",
            "*.xcodeproj",
            "Pods",
            ".gradle",
            
            // Database
            "*.db",
            "*.sqlite",
            "*.sqlite3",
            
            // Media files (optional - comment out if needed)
            "*.jpg",
            "*.jpeg",
            "*.png",
            "*.gif",
            "*.svg",
            "*.ico",
            "*.mp4",
            "*.mp3",
            "*.pdf",
            
            // Other
            ".sass-cache",
            "*.map",
            "*.min.js",
            "*.min.css",
        ]

        // Create ignore instance
        const ig = ignore().add(DEFAULT_EXCLUDE)

        // Helper to check if file matches include patterns
        const matchesIncludePattern = (path: string): boolean => {
            const fileName = path.split('/').pop() || ''
            return DEFAULT_INCLUDE.some(pattern => {
                const regex = new RegExp('^' + pattern.replace(/\*/g, '.*') + '$')
                return regex.test(fileName)
            })
        }

        const formData = new FormData()
        let kept = 0
        
        Array.from(files).forEach(file => {
            const rel = (file as any).webkitRelativePath || file.name
            
            // Check if file should be excluded
            if (ig.ignores(rel)) {
                return
            }
            
            // Check if file matches include patterns
            if (!matchesIncludePattern(rel)) {
                return
            }
            
            formData.append('files', file)
            kept += 1
        })

        if (kept === 0) {
            throw new Error('No files matched the allowed extensions (check include/exclude patterns).')
        }

        const res = await fetch(`${API_BASE}/folders/import`, {
            method: 'POST',
            body: formData
        })
        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: 'Failed to import project' }))
            throw new Error(error.detail || 'Failed to import project')
        }
        return res.json()
    },

    async discoverFolders() {
        const res = await fetch(`${API_BASE}/folders/discover`, {
            method: 'POST'
        })
        if (!res.ok) throw new Error('Failed to discover folders')
        return res.json()
    },

    async addFolder(path: string) {
        const res = await fetch(`${API_BASE}/folders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        })
        if (!res.ok) throw new Error('Failed to add folder')
        return res.json()
    },

    async deleteFolder(id: number) {
        const res = await fetch(`${API_BASE}/folders/${id}`, {
            method: 'DELETE'
        })
        if (!res.ok) throw new Error('Failed to delete folder')
        return res.json()
    },

    async startIndexing(folderId: number, incremental = true) {
        const res = await fetch(`${API_BASE}/folders/${folderId}/index`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ incremental })
        })
        if (!res.ok) throw new Error('Failed to start indexing')
        return res.json()
    },

    async search(
        query: string,
        folderId: number,
        filePaths?: { path: string; start_line?: number; end_line?: number }[],
        topK = 10
    ) {
        const res = await fetch(`${API_BASE}/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                folder_id: folderId,
                file_paths: filePaths || [],
                top_k: topK
            })
        })
        if (!res.ok) throw new Error('Search failed')
        return res.json()
    },

    async generateContext(
        query: string,
        folderId: number,
        filePaths?: { path: string; start_line?: number; end_line?: number }[],
        topK = 10
    ) {
        const res = await fetch(`${API_BASE}/context`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                folder_id: folderId,
                file_paths: filePaths || [],
                top_k: topK
            })
        })
        if (!res.ok) throw new Error('Context generation failed')
        return res.json()
    },

    async getFolderTree(folderId: number) {
        console.log('[API] Fetching folder tree for folderId:', folderId)
        const res = await fetch(`${API_BASE}/folders/${folderId}/tree`)
        
        console.log('[API] Response status:', res.status, 'Content-Type:', res.headers.get('content-type'))
        
        // Clone response for potential error reading
        const resClone = res.clone()
        
        // Check content type first
        const contentType = res.headers.get('content-type') || ''
        const isJson = contentType.includes('application/json')
        
        if (!res.ok) {
            // Try to get error message from response
            let errorMessage = `Failed to load file tree (Status: ${res.status})`
            try {
                if (isJson) {
                    const errorData = await res.json()
                    errorMessage = errorData.detail || errorData.message || errorMessage
                } else {
                    const text = await res.text()
                    console.error('[API] Non-JSON error response:', text.substring(0, 500))
                    errorMessage = `Server error: ${text.substring(0, 100)} (Status: ${res.status})`
                }
            } catch (e) {
                console.error('[API] Error parsing error response:', e)
                try {
                    const text = await resClone.text()
                    errorMessage = `Error: ${text.substring(0, 100)} (Status: ${res.status})`
                } catch (e2) {
                    // Ignore
                }
            }
            throw new Error(errorMessage)
        }
        
        // Check if response is actually JSON
        if (!isJson) {
            const text = await res.text()
            console.error('[API] Non-JSON response received:', {
                contentType,
                status: res.status,
                url: `${API_BASE}/folders/${folderId}/tree`,
                text: text.substring(0, 500)
            })
            throw new Error(`Expected JSON but received ${contentType}. Response: ${text.substring(0, 100)}`)
        }
        
        try {
            const text = await res.text()
            console.log('[API] Response text preview:', text.substring(0, 200))
            const data = JSON.parse(text)
            console.log('[API] Parsed JSON successfully')
            return data
        } catch (e) {
            console.error('[API] JSON parse error:', e)
            const text = await resClone.text().catch(() => 'Unable to read response')
            console.error('[API] Full response text:', text)
            throw new Error(`Failed to parse JSON response: ${e}. Response preview: ${text.substring(0, 500)}`)
        }
    },

    async getFileContent(folderId: number, path: string) {
        const res = await fetch(`${API_BASE}/folders/${folderId}/file?path=${encodeURIComponent(path)}`)
        if (!res.ok) throw new Error('Failed to load file')
        return res.json()
    }
}