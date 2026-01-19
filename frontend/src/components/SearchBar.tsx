import { useState, useRef } from 'react'
import { api } from '../services/api'

interface AttachedFile {
    path: string
    name: string
}

interface Props {
    activeFolderId: number | null
}

export default function SearchBar({ activeFolderId }: Props) {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState<any[]>([])
    const [prompts, setPrompts] = useState<string[]>([])
    const [activePart, setActivePart] = useState(0)
    const [tokenCount, setTokenCount] = useState<number>(0)
    const [loadingAction, setLoadingAction] = useState<string | null>(null)
    const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([])
    const [isDragging, setIsDragging] = useState(false)
    const chatInputRef = useRef<HTMLTextAreaElement>(null)
    const isLoading = !!loadingAction

    const handleSearch = async () => {
        if (!query.trim()) return
        if (!activeFolderId) {
            alert('Please select a project first')
            return
        }

        setLoadingAction('search')
        setPrompts([])
        try {
            const data = await api.search(query, activeFolderId)
            setResults(data.results || [])
        } catch (error) {
            alert('Search failed: ' + error)
        } finally {
            setLoadingAction(null)
        }
    }

    const handleGenerate = async () => {
        if (!query.trim()) return

        setLoadingAction('generate')
        setResults([])
        setPrompts([])
        try {
            const data = await api.generateContext(query)
            setPrompts(data.prompts || [])
            setActivePart(0)
            setTokenCount(data.total_tokens || 0)
        } catch (error) {
            alert('Generation failed: ' + error)
        } finally {
            setLoadingAction(null)
        }
    }

    const copyPrompt = () => {
        const text = prompts[activePart]
        if (text) {
            navigator.clipboard.writeText(text)
            alert(`Copied Part ${activePart + 1} to clipboard!`)
        }
    }

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

        const filePath = e.dataTransfer.getData('text/plain')
        if (filePath) {
            const fileName = filePath.split('/').pop() || filePath
            if (!attachedFiles.find(f => f.path === filePath)) {
                setAttachedFiles([...attachedFiles, { path: filePath, name: fileName }])
            }
        }
    }

    const removeFile = (path: string) => {
        setAttachedFiles(attachedFiles.filter(f => f.path !== path))
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

        // Format query with attached files
        let finalQuery = query
        if (attachedFiles.length > 0) {
            const fileRefs = attachedFiles.map(f => `@${f.path}`).join(' ')
            finalQuery = fileRefs + (query.trim() ? ` ${query}` : '')
        }

        setLoadingAction('search')
        setPrompts([])
        try {
            const data = await api.search(finalQuery, activeFolderId)
            setResults(data.results || [])
            setQuery('')
            setAttachedFiles([])
        } catch (error) {
            alert('Search failed: ' + error)
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
            {/* Chat messages area */}
            <div style={{ 
                flex: 1, 
                overflowY: 'auto', 
                marginBottom: '1rem',
                padding: '1rem',
                background: 'var(--bg-secondary)',
                borderRadius: '8px',
                border: '1px solid var(--border-color)'
            }}>
                {results.length > 0 ? (
                    <div>
                        <div style={{ marginBottom: '0.5rem', fontWeight: 500, color: 'var(--text-secondary)' }}>
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
                                <div style={{ fontSize: '0.85em', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
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
                ) : (
                    !isLoading && (
                        <div style={{ 
                            color: 'var(--text-secondary)', 
                            textAlign: 'center', 
                            padding: '2rem',
                            fontSize: '0.9em'
                        }}>
                            {prompts.length === 0 ? 'Start a conversation...' : ''}
                        </div>
                    )
                )}
            </div>

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
                                <span style={{ color: 'var(--text-primary)' }}>@{file.path}</span>
                                <button
                                    onClick={() => removeFile(file.path)}
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
                        {loadingAction === 'search' && <span className="spinner"></span>}
                        Send
                    </button>
                </div>
            </div>

            {/* Generated prompts */}
            {prompts.length > 0 && (
                <div className="card" style={{ marginTop: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', alignItems: 'center' }}>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                            <div style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>Generated Context</div>
                            {prompts.length > 1 && prompts.map((_, i) => (
                                <button
                                    key={i}
                                    onClick={() => setActivePart(i)}
                                    style={{
                                        padding: '0.2rem 0.6rem',
                                        fontSize: '0.8em',
                                        background: activePart === i ? 'var(--accent-color)' : 'transparent',
                                        color: activePart === i ? '#fff' : 'var(--text-secondary)',
                                        border: '1px solid var(--border-color)',
                                        borderRadius: '4px',
                                        cursor: 'pointer'
                                    }}
                                >
                                    Part {i + 1}
                                </button>
                            ))}
                        </div>
                        <button onClick={copyPrompt} style={{ fontSize: '0.85em', padding: '0.2em 0.8em' }}>
                            Copy Part {activePart + 1}
                        </button>
                    </div>
                    <textarea
                        value={prompts[activePart] || ''}
                        readOnly
                        style={{
                            width: '100%',
                            height: '300px',
                            padding: '0.5rem',
                            borderRadius: '4px',
                            border: '1px solid var(--border-color)',
                            background: 'var(--bg-tertiary)',
                            color: 'var(--text-primary)',
                            fontFamily: 'monospace',
                            fontSize: '0.9em',
                            resize: 'vertical'
                        }}
                    />
                    <div style={{ marginTop: '0.5rem', fontSize: '0.85em', color: 'var(--text-secondary)' }}>
                        Total Estimated Tokens: <strong>{tokenCount}</strong>
                        {prompts.length > 1 && (
                            <span style={{ marginLeft: '1rem', color: '#d97706', fontWeight: 500 }}>
                                ℹ️ Split into {prompts.length} parts (Too large for one message)
                            </span>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
