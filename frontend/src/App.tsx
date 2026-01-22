import { useState, useEffect, useRef } from 'react'
import './App.css'
import FolderList from './components/FolderList'
import SearchBar from './components/SearchBar'
import FileTree from './components/FileTree'
import { api } from './services/api'

interface Folder {
    id: number
    path: string
    name: string
    status: string
    total_files: number
    indexed_files: number
    total_chunks: number
}

function App() {
    const [folders, setFolders] = useState<Folder[]>([])
    const [loading, setLoading] = useState(false)
    const [activeFolderId, setActiveFolderId] = useState<number | null>(() => {
        const saved = localStorage.getItem('activeFolderId')
        return saved ? parseInt(saved, 10) : null
    })
    const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null)
    const [fileContent, setFileContent] = useState<string>('')
    const [fileError, setFileError] = useState<string | null>(null)
    const [fileLoading, setFileLoading] = useState(false)
    const fileViewerRef = useRef<HTMLPreElement | null>(null)
    const abortControllerRef = useRef<AbortController | null>(null)

    useEffect(() => {
        loadFolders()
    }, [])

    useEffect(() => {
        if (activeFolderId !== null) {
            localStorage.setItem('activeFolderId', activeFolderId.toString())
        } else {
            localStorage.removeItem('activeFolderId')
        }
    }, [activeFolderId])

    // ✅ Cleanup khi unmount
    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort()
            }
        }
    }, [])

    const loadFolders = async () => {
        setLoading(true)
        try {
            const data = await api.getFolders()
            setFolders(data)
            
            if (activeFolderId === null && data.length === 1) {
                setActiveFolderId(data[0].id)
            } else if (activeFolderId !== null && !data.find((f: Folder) => f.id === activeFolderId)) {
                setActiveFolderId(null)
                if (data.length === 1) {
                    setActiveFolderId(data[0].id)
                }
            }
        } catch (error) {
            console.error('Failed to load folders:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleFileDrag = (filePath: string) => {
        console.log('File dragged:', filePath)
    }

    const handleSelectFile = async (filePath: string) => {
        if (!activeFolderId) return
        
        // Toggle off nếu click vào file đang mở
        if (selectedFilePath === filePath) {
            // ✅ Hủy request đang chạy (nếu có)
            if (abortControllerRef.current) {
                abortControllerRef.current.abort()
                abortControllerRef.current = null
            }
            setSelectedFilePath(null)
            setFileContent('')
            setFileError(null)
            setFileLoading(false)
            return
        }

        // ✅ HỦY REQUEST CŨ trước khi load file mới
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
        }

        // ✅ Tạo AbortController mới
        const controller = new AbortController()
        abortControllerRef.current = controller

        setSelectedFilePath(filePath)
        setFileLoading(true)
        setFileError(null)
        
        try {
            // ✅ Truyền signal vào API (cần update api.getFileContent)
            const data = await api.getFileContent(activeFolderId, filePath)
            
            // ✅ Chỉ update nếu request không bị hủy
            if (!controller.signal.aborted) {
                setFileContent(data.content)
            }
        } catch (err) {
            // ✅ Bỏ qua lỗi AbortError
            if (err instanceof Error && err.name === 'AbortError') {
                console.log('Request cancelled:', filePath)
                return
            }
            
            const msg = err instanceof Error ? err.message : 'Failed to load file'
            if (!controller.signal.aborted) {
                setFileError(msg)
                setFileContent('')
            }
        } finally {
            if (!controller.signal.aborted) {
                setFileLoading(false)
            }
            // Cleanup
            if (abortControllerRef.current === controller) {
                abortControllerRef.current = null
            }
        }
    }

    const handleCodeDragStart = (e: any) => {
        // If user has a text selection inside the file viewer, send only "file:start-end"
        if (!selectedFilePath || !fileViewerRef.current) return
        const sel = window.getSelection()
        if (!sel || sel.rangeCount === 0) {
            e.dataTransfer.setData('text/plain', selectedFilePath)
            return
        }
        const range = sel.getRangeAt(0)
        if (sel.isCollapsed) {
            e.dataTransfer.setData('text/plain', selectedFilePath)
            return
        }
        // Ensure selection is within the file viewer
        if (!fileViewerRef.current.contains(range.commonAncestorContainer)) {
            e.dataTransfer.setData('text/plain', selectedFilePath)
            return
        }

        const startOffset = range.startOffset
        const endOffset = range.endOffset
        const s = Math.min(startOffset, endOffset)
        const t = Math.max(startOffset, endOffset)

        const startLine = fileContent.slice(0, s).split('\n').length
        const endLine = fileContent.slice(0, t).split('\n').length
        e.dataTransfer.setData('text/plain', `${selectedFilePath}:${startLine}-${endLine}`)
    }

    return (
        <div className="container">
            <div className="sidebar" style={{ width: '250px' }}>
                <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>CursorLite</h2>
                <div style={{ marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
                    <div style={{ fontSize: '0.85em', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                        Projects
                    </div>
                    <FolderList 
                        folders={folders} 
                        activeFolderId={activeFolderId}
                        onUpdate={loadFolders}
                        onSelectFolder={setActiveFolderId}
                    />
                </div>
                <div style={{ 
                    borderTop: '1px solid var(--border-color)', 
                    paddingTop: '1rem',
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    minHeight: 0,
                    overflow: 'hidden'
                }}>
                    <div style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        fontSize: '0.85em', 
                        color: 'var(--text-secondary)', 
                        marginBottom: '0.5rem' 
                    }}>
                        <span>File Tree</span>
                    </div>
                    <div style={{ 
                        flex: 1, 
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column',
                        minHeight: 0
                    }}>
                        <FileTree 
                            folderId={activeFolderId} 
                            onFileDrag={handleFileDrag}
                            onFileSelect={handleSelectFile}
                            selectedPath={selectedFilePath}
                        />
                    </div>
                </div>
            </div>
            
            <div 
                className="main-content" 
                style={{ 
                    display: 'grid', 
                    gridTemplateColumns: selectedFilePath ? '1fr 1fr' : '1fr',
                    gap: '1rem', 
                    width: 'calc(100% - 250px)' 
                }}
            >
                {/* File Viewer - BÊN TRÁI (chỉ hiển thị khi đã chọn file) */}
                {selectedFilePath && (
                    <div style={{ 
                        border: '1px solid var(--border-color)', 
                        borderRadius: '6px',
                        padding: '1rem',
                        minWidth: 0,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.5rem',
                        overflow: 'hidden'
                    }}>
                        <div style={{ 
                            fontWeight: 600, 
                            color: 'var(--text-primary)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem'
                        }}>
                            <span>{selectedFilePath}</span>
                            {fileLoading && (
                                <span className="spinner" style={{ fontSize: '0.8em' }}></span>
                            )}
                        </div>

                        {fileLoading ? (
                            <div style={{ color: 'var(--text-secondary)' }}>
                                <span className="spinner"></span>
                                Loading file...
                            </div>
                        ) : fileError ? (
                            <div style={{ color: '#dc2626' }}>Error: {fileError}</div>
                        ) : (
                            <pre
                                ref={fileViewerRef}
                                style={{ 
                                margin: 0, 
                                whiteSpace: 'pre-wrap', 
                                wordBreak: 'break-word', 
                                fontFamily: 'monospace',
                                fontSize: '0.9em',
                                overflow: 'auto',
                                    flex: 1,
                                    userSelect: 'text'
                            }}
                            onDragStart={handleCodeDragStart}
                            >
                                {fileContent}
                            </pre>
                        )}
                    </div>
                )}
                
                {/* Chat Box - BÊN PHẢI (không chọn file => chiếm full width) */}
                <div style={{ 
                    border: '1px solid var(--border-color)', 
                    borderRadius: '6px',
                    padding: '1rem',
                    minWidth: 0,
                    overflow: 'hidden'
                }}>
                    <SearchBar activeFolderId={activeFolderId} />
                </div>
            </div>
        </div>
    )
}

export default App