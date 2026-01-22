import { useState, useRef } from 'react'
import { api } from '../services/api'
import ContextViewer from './ContextViewer'

interface AttachedFile {
    path: string
    name: string
    startLine?: number
    endLine?: number
}

interface Props {
    activeFolderId: number | null
}

export default function SearchBar({ activeFolderId }: Props) {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState<any[]>([])
    const [prompts, setPrompts] = useState<string[]>([])
    const [tokenCounts, setTokenCounts] = useState<number[]>([])
    const [loadingAction, setLoadingAction] = useState<string | null>(null)
    const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([])
    const [isDragging, setIsDragging] = useState(false)
    const chatInputRef = useRef<HTMLTextAreaElement>(null)
    const isLoading = !!loadingAction

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragging(true)
    }

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragging(false)
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragging(false)

        const dropped = e.dataTransfer.getData('text/plain')?.trim()
        if (!dropped) return

        // Support "path:start-end" for code selections (Cursor-like)
        const m = dropped.match(/^(.*):(\d+)-(\d+)$/)
        if (m) {
            const path = m[1]
            const startLine = parseInt(m[2], 10)
            const endLine = parseInt(m[3], 10)
            const name = path.split('/').pop() || path
            const key = `${path}:${startLine}-${endLine}`
            if (!attachedFiles.find(f => (f.startLine && f.endLine) ? `${f.path}:${f.startLine}-${f.endLine}` === key : f.path === key)) {
                setAttachedFiles([...attachedFiles, { path, name, startLine, endLine }])
            }
            return
        }

        // Fallback: plain file path
        const filePath = dropped
        const fileName = filePath.split('/').pop() || filePath
        if (!attachedFiles.find(f => f.path === filePath && !f.startLine && !f.endLine)) {
            setAttachedFiles([...attachedFiles, { path: filePath, name: fileName }])
        }
    }

    const removeFile = (path: string, startLine?: number, endLine?: number) => {
        const key = (typeof startLine === 'number' && typeof endLine === 'number')
            ? `${path}:${startLine}-${endLine}`
            : path
        setAttachedFiles(attachedFiles.filter(f => {
            const k = (typeof f.startLine === 'number' && typeof f.endLine === 'number')
                ? `${f.path}:${f.startLine}-${f.endLine}`
                : f.path
            return k !== key
        }))
    }

    const getFileIcon = (fileName: string): string => {
        const ext = fileName.split('.').pop()?.toLowerCase()
        const iconMap: { [key: string]: string } = {
            'py': '🐍', 'js': '📜', 'ts': '📘', 'jsx': '⚛️', 'tsx': '⚛️',
            'html': '🌐', 'css': '🎨', 'json': '📋', 'md': '📝',
            'yml': '⚙️', 'yaml': '⚙️', 'xml': '📄', 'txt': '📄',
            'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️', 'svg': '🖼️',
            'pdf': '📕', 'zip': '📦', 'tar': '📦', 'gz': '📦',
            'sh': '💻', 'bash': '💻', 'zsh': '💻',
            'go': '🐹', 'rs': '🦀', 'java': '☕', 'cpp': '⚙️', 'c': '⚙️',
            'php': '🐘', 'rb': '💎', 'swift': '🐦', 'kt': '🟣'
        }
        return iconMap[ext || ''] || '📄'
    }

    const handleSendMessage = async () => {
        if (!query.trim() && attachedFiles.length === 0) return
        if (!activeFolderId) {
            alert('Please select a project first')
            return
        }

        let finalQuery = query
        if (attachedFiles.length > 0) {
            const fileRefs = attachedFiles.map(f => {
                if (typeof f.startLine === 'number' && typeof f.endLine === 'number') {
                    return `@${f.path}:${f.startLine}-${f.endLine}`
                }
                return `@${f.path}`
            }).join(' ')
            finalQuery = fileRefs + (query.trim() ? ` ${query}` : '')
        }

        // Map attached files to backend schema
        const filePaths = attachedFiles.map(f => ({
            path: f.path,
            start_line: typeof f.startLine === 'number' ? f.startLine : undefined,
            end_line: typeof f.endLine === 'number' ? f.endLine : undefined
        }))

        setLoadingAction('context')
        setResults([])
        setPrompts([])
        setTokenCounts([])
        try {
            const data = await api.generateContext(finalQuery, activeFolderId, filePaths)
            if (data.prompts && Array.isArray(data.prompts)) {
                const promptOutputs = data.prompts.map((p: any) => p.prompt_output || p)
                const tokens = data.prompts.map((p: any) => p.tokens || 0)
                setPrompts(promptOutputs)
                setTokenCounts(tokens)
            }
        } catch (error) {
            alert('Context generation failed: ' + error)
        } finally {
            setLoadingAction(null)
        }
    }

    return (
        <div style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            height: '100%',
            maxHeight: 'calc(100vh - 2rem)'
        }}>
            {/* Context Viewer Component */}
            <ContextViewer 
                prompts={prompts} 
                tokenCounts={tokenCounts}
            />

            {/* Spacer or Chat messages area */}
            {results.length > 0 ? (
                <div style={{ 
                    flex: 1, 
                    overflowY: 'auto', 
                    marginBottom: '1rem',
                    padding: '1rem',
                    background: 'var(--bg-secondary)',
                    borderRadius: '8px',
                    border: '1px solid var(--border-color)'
                }}>
                    <div>
                        <div style={{ 
                            marginBottom: '0.5rem', 
                            fontWeight: 500, 
                            color: 'var(--text-secondary)' 
                        }}>
                            Search Results ({results.length})
                        </div>
                        {results.map((result, idx) => (
                            <div key={idx} style={{
                                padding: '1rem',
                                marginBottom: '0.5rem',
                                background: 'var(--bg-tertiary)',
                                borderRadius: '8px',
                                border: '1px solid var(--border-color)'
                            }}>
                                <div style={{ 
                                    fontSize: '0.85em', 
                                    color: 'var(--text-secondary)', 
                                    marginBottom: '0.5rem' 
                                }}>
                                    {result.file_path}:{result.start_line}-{result.end_line} (score: {result.score.toFixed(4)})
                                </div>
                                <pre style={{
                                    background: 'var(--bg-secondary)',
                                    padding: '0.5rem',
                                    borderRadius: '4px',
                                    overflow: 'auto',
                                    fontSize: '0.85em',
                                    border: '1px solid var(--border-color)',
                                    margin: 0
                                }}>
                                    {result.text}
                                </pre>
                            </div>
                        ))}
                    </div>
                </div>
            ) : (
                <div style={{ flex: 1 }} />
            )}

            {/* Chat input area */}
            <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                style={{
                    border: `2px dashed ${isDragging ? 'var(--accent-color)' : 'var(--border-color)'}`,
                    borderRadius: '8px',
                    padding: '1rem',
                    background: isDragging ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
                    transition: 'all 0.2s'
                }}
            >
                {/* Attached files */}
                {attachedFiles.length > 0 && (
                    <div style={{ 
                        display: 'flex', 
                        gap: '0.5rem', 
                        marginBottom: '0.5rem',
                        flexWrap: 'wrap'
                    }}>
                        {attachedFiles.map((file, idx) => (
                            <div
                                key={idx}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.25rem',
                                    padding: '0.25rem 0.5rem',
                                    background: 'var(--bg-tertiary)',
                                    borderRadius: '4px',
                                    fontSize: '0.85em',
                                    border: '1px solid var(--border-color)'
                                }}
                            >
                                <span>{getFileIcon(file.name)}</span>
                                <span style={{ color: 'var(--text-primary)' }}>
                                    @{file.path}
                                    {typeof file.startLine === 'number' && typeof file.endLine === 'number'
                                        ? `:${file.startLine}-${file.endLine}`
                                        : ''}
                                </span>
                                <button
                                    onClick={() => removeFile(file.path, file.startLine, file.endLine)}
                                    style={{
                                        background: 'transparent',
                                        border: 'none',
                                        cursor: 'pointer',
                                        padding: '0',
                                        fontSize: '0.9em',
                                        color: 'var(--text-secondary)',
                                        marginLeft: '0.25rem'
                                    }}
                                >
                                    ×
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}>
                    <textarea
                        ref={chatInputRef}
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyPress={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault()
                                handleSendMessage()
                            }
                        }}
                        placeholder="Type your message..."
                        style={{
                            flex: 1,
                            minHeight: '60px',
                            maxHeight: '200px',
                            resize: 'vertical',
                            padding: '0.75rem',
                            borderRadius: '6px',
                            border: '1px solid var(--border-color)',
                            background: 'var(--bg-primary)',
                            color: 'var(--text-primary)',
                            fontFamily: 'inherit',
                            fontSize: '0.9em'
                        }}
                    />
                    <button
                        onClick={handleSendMessage} 
                        disabled={isLoading || (!query.trim() && attachedFiles.length === 0)}
                        style={{
                            padding: '0.75rem 1.5rem',
                            height: 'fit-content',
                            backgroundColor: 'var(--accent-color)',
                            color: '#fff',
                            borderColor: 'var(--accent-color)'
                        }}
                    >
                        {isLoading && <span className="spinner"></span>}
                        Send
                    </button>
                </div>
            </div>
        </div>
    )
}