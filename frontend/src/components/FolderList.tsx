import React from 'react'
import { api } from '../services/api'

interface Folder {
    id: number
    path: string
    name: string
    status: string
    total_files: number
    indexed_files: number
    total_chunks: number
}

interface Props {
    folders: Folder[]
    activeFolderId: number | null
    onUpdate: () => void
    onSelectFolder: (folderId: number | null) => void
}

export default function FolderList({ folders, activeFolderId, onUpdate, onSelectFolder }: Props) {
    const fileInputRef = React.useRef<HTMLInputElement>(null)
    const dropdownRef = React.useRef<HTMLDivElement>(null)
    const [isDropdownOpen, setIsDropdownOpen] = React.useState(false)

    const activeFolder = folders.find(f => f.id === activeFolderId)

    // Close dropdown when clicking outside
    React.useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsDropdownOpen(false)
            }
        }

        if (isDropdownOpen) {
            document.addEventListener('mousedown', handleClickOutside)
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside)
        }
    }, [isDropdownOpen])

    const handleImportClick = () => {
        fileInputRef.current?.click()
    }

    const handleToggleDropdown = () => {
        setIsDropdownOpen(!isDropdownOpen)
    }

    const handleSelectFolder = (folderId: number | null) => {
        onSelectFolder(folderId === activeFolderId ? null : folderId)
        setIsDropdownOpen(false)
    }

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files
        if (!files || files.length === 0) return

        try {
            console.log(`[Import] Starting import of ${files.length} files...`)
            const result = await api.importProject(files)
            console.log('[Import] Project imported:', result)
            
            // Refresh folder list immediately
            onUpdate()
            
            // Listen to SSE for indexing progress
            const folderId = result.folder_id
            console.log(`[Import] Listening to indexing progress for folder ${folderId}`)
            
            const eventSource = new EventSource(`/api/folders/${folderId}/index/progress`)
            
            eventSource.addEventListener('progress', (event: MessageEvent) => {
                try {
                    const data = JSON.parse(event.data)
                    console.log('[Import] Indexing progress:', data)
                    if (data.status === 'indexed' || data.status === 'error') {
                        eventSource.close()
                        onUpdate()
                        if (data.status === 'indexed') {
                            console.log('[Import] Indexing completed, selecting folder')
                            onSelectFolder(folderId)
                        } else {
                            console.error('[Import] Indexing error:', data.error)
                            alert(`Indexing failed: ${data.error || 'Unknown error'}`)
                        }
                    }
                } catch (e) {
                    console.error('Error parsing SSE data:', e)
                }
            })
            
            eventSource.onerror = (err) => {
                console.error('[Import] SSE error:', err)
                eventSource.close()
            }
            
            // Poll for updates as fallback
            const pollInterval = setInterval(() => {
                onUpdate()
            }, 2000)
            
            setTimeout(() => {
                clearInterval(pollInterval)
                eventSource.close()
            }, 300000) // 5 minutes timeout
            
        } catch (error) {
            console.error('[Import] Failed to import project:', error)
            alert(`Failed to import project: ${error instanceof Error ? error.message : 'Unknown error'}`)
        } finally {
            if (fileInputRef.current) {
                fileInputRef.current.value = ''
            }
        }
    }

    return (
        <div ref={dropdownRef} style={{ position: 'relative' }}>
            <input
                ref={fileInputRef}
                type="file"
                webkitdirectory=""
                directory=""
                multiple
                style={{ display: 'none' }}
                onChange={handleFileChange}
            />
            <button onClick={handleImportClick} style={{ width: '100%', marginBottom: '0.75rem', fontSize: '0.85em' }}>
                📁 Import Project
            </button>

            {/* Current Project Display */}
            <div
                onClick={handleToggleDropdown}
                style={{
                    padding: '0.75rem',
                    background: activeFolder ? 'var(--accent-color)' : 'var(--bg-secondary)',
                    color: activeFolder ? '#fff' : 'var(--text-primary)',
                    borderRadius: '6px',
                    border: `1px solid ${activeFolder ? 'var(--accent-color)' : 'var(--border-color)'}`,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: isDropdownOpen ? '0.5rem' : '0'
                }}
                onMouseEnter={(e) => {
                    if (!activeFolder) {
                        e.currentTarget.style.background = 'var(--bg-tertiary)'
                        e.currentTarget.style.borderColor = 'var(--accent-color)'
                    }
                }}
                onMouseLeave={(e) => {
                    if (!activeFolder) {
                        e.currentTarget.style.background = 'var(--bg-secondary)'
                        e.currentTarget.style.borderColor = 'var(--border-color)'
                    }
                }}
            >
                <div style={{ flex: 1, minWidth: 0 }}>
                    {activeFolder ? (
                        <>
                            <div style={{ 
                                fontWeight: 500, 
                                fontSize: '0.9em',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap'
                            }}>
                                {activeFolder.name}
                            </div>
                            <div style={{ 
                                fontSize: '0.75em', 
                                opacity: 0.9,
                                marginTop: '0.125rem'
                            }}>
                                <span style={{
                                    color: activeFolder.status === 'indexed' ? '#16a34a' : 
                                           activeFolder.status === 'indexing' ? '#3b82f6' : '#d97706',
                                    fontWeight: 500
                                }}>
                                    {activeFolder.status}
                                </span>
                            </div>
                        </>
                    ) : (
                        <div style={{ 
                            fontSize: '0.9em',
                            opacity: 0.7
                        }}>
                            Select a project...
                        </div>
                    )}
                </div>
                <span style={{
                    marginLeft: '0.5rem',
                    fontSize: '0.8em',
                    transition: 'transform 0.2s',
                    transform: isDropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)'
                }}>
                    ▼
                </span>
            </div>

            {/* Dropdown List */}
            {isDropdownOpen && (
                <div style={{
                    position: 'absolute',
                    top: '100%',
                    left: 0,
                    right: 0,
                    marginTop: '0.5rem',
                    maxHeight: '250px',
                    overflowY: 'auto',
                    overflowX: 'hidden',
                    paddingRight: '0.25rem',
                    scrollbarWidth: 'thin',
                    scrollbarColor: 'var(--border-color) transparent',
                    border: '1px solid var(--border-color)',
                    borderRadius: '6px',
                    background: 'var(--bg-secondary)',
                    padding: '0.25rem',
                    zIndex: 1000,
                    boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
                }}
                className="scrollable-list"
                >
                {folders.map(folder => (
                        <div 
                            key={folder.id}
                            onClick={() => handleSelectFolder(folder.id)}
                            style={{
                                padding: '0.5rem 0.75rem',
                                marginBottom: '0.125rem',
                                background: folder.id === activeFolderId ? 'var(--accent-color)' : 'transparent',
                                color: folder.id === activeFolderId ? '#fff' : 'var(--text-primary)',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                transition: 'all 0.2s',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between'
                            }}
                            onMouseEnter={(e) => {
                                if (folder.id !== activeFolderId) {
                                    e.currentTarget.style.background = 'var(--bg-tertiary)'
                                }
                            }}
                            onMouseLeave={(e) => {
                                if (folder.id !== activeFolderId) {
                                    e.currentTarget.style.background = 'transparent'
                                }
                            }}
                        >
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ 
                                    fontWeight: folder.id === activeFolderId ? 600 : 500, 
                                    fontSize: '0.85em',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap'
                                }}>
                                    {folder.name}
                        </div>
                                <div style={{ 
                                    fontSize: '0.7em', 
                                    opacity: 0.8,
                                    marginTop: '0.125rem'
                                }}>
                                    <span style={{
                                        color: folder.status === 'indexed' ? '#16a34a' : 
                                               folder.status === 'indexing' ? '#3b82f6' : '#d97706',
                                        fontWeight: 500
                            }}>
                                {folder.status}
                            </span>
                        </div>
                            </div>
                            {folder.id === activeFolderId && (
                                <span style={{ marginLeft: '0.5rem', fontSize: '0.7em' }}>✓</span>
                            )}
                        </div>
                    ))}
                    {folders.length === 0 && (
                        <div style={{
                            padding: '1rem',
                            textAlign: 'center',
                            color: 'var(--text-secondary)',
                            fontSize: '0.85em'
                        }}>
                            No projects yet
                    </div>
                    )}
            </div>
            )}
        </div>
    )
}
