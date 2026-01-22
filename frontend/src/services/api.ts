const API_BASE = '/api'

export const api = {
    async getFolders() {
        const res = await fetch(`${API_BASE}/folders`)
        if (!res.ok) throw new Error('Failed to fetch folders')
        return res.json()
    },

    async importProject(files: FileList) {
        const DEFAULT_INCLUDE_RAW = [
            "*.py", "*.js", "*.ts", "*.tsx", "*.jsx",
            "*.go", "*.java", "*.kt", "*.cs",
            "*.rb", "*.php", "*.rs",
            "*.c", "*.h", "*.cpp", "*.hpp",
            "*.swift",
            "*.txt", "*.yaml", "*.yml", "*.json",
        ]

        const DEFAULT_EXCLUDE_RAW = [
            ".git/**",
            "node_modules/**",
            "dist/**",
            "build/**",
            ".venv/**",
            "venv/**",
            "__pycache__/**",
            ".cursorlite/**",
            "target/**",
            ".next/**",
            ".idea/**",
            ".vscode/**",
            ".env",
            ".env.*",
        ]

        // Mirror backend/src/config.py expand_pattern behavior so nested paths match too.
        const expandPattern = (pattern: string): string[] => {
            const p = pattern.trim()
            if (!p || p.startsWith('#')) return []
            if (p.startsWith('**/')) return [p]
            if (p.startsWith('*.')) return [p, `**/${p}`]
            if (p.includes('/**')) return [p, `**/${p}`]
            return [p]
        }

        const expandPatterns = (patterns: string[]): string[] => {
            const out: string[] = []
            const seen = new Set<string>()
            for (const p of patterns) {
                for (const ep of expandPattern(p)) {
                    if (!seen.has(ep)) {
                        seen.add(ep)
                        out.push(ep)
                    }
                }
            }
            return out
        }

        const globToRegExp = (pattern: string): RegExp => {
            // Escape regex specials, then translate globs (*, **) to regex.
            const escaped = pattern
                .replace(/[.+^${}()|[\]\\]/g, "\\$&")
                .replace(/\*\*/g, "§§DOUBLESTAR§§")
                .replace(/\*/g, "[^/]*")
                .replace(/§§DOUBLESTAR§§/g, ".*")
            return new RegExp(`^${escaped}$`)
        }

        const includeRegs = expandPatterns(DEFAULT_INCLUDE_RAW).map(globToRegExp)
        const excludeRegs = expandPatterns(DEFAULT_EXCLUDE_RAW).map(globToRegExp)

        const shouldInclude = (path: string): boolean => {
            // Exclude first
            if (excludeRegs.some(re => re.test(path))) return false
            // Include list: if none match, skip
            if (!includeRegs.some(re => re.test(path))) return false
            return true
        }

        const formData = new FormData()
        let kept = 0
        Array.from(files).forEach(file => {
            const rel = (file as any).webkitRelativePath || file.name
            if (shouldInclude(rel)) {
                formData.append('files', file)
                kept += 1
            }
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