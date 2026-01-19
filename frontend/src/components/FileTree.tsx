import React, { useState, useEffect } from 'react'
import { api } from '../services/api'

interface FileTreeNode {
    name: string
    path: string
    type: 'file' | 'directory'
    children?: FileTreeNode[]
}

interface Props {
    folderId: number | null
    onFileDrag?: (filePath: string) => void
}

function getFileIcon(fileName: string): string {
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

function TreeNode({ 
    node, 
    level = 0, 
    basePath = '',
    onFileDrag 
}: { 
    node: FileTreeNode
    level?: number
    basePath?: string
    onFileDrag?: (filePath: string) => void
}) {
    const [isExpanded, setIsExpanded] = useState(level < 2)
    const isDirectory = node.type === 'directory'
    const hasChildren = node.children && node.children.length > 0
    const fullPath = basePath && basePath !== node.name 
        ? `${basePath}/${node.path || node.name}` 
        : (node.path || node.name)

    const handleDragStart = (e: React.DragEvent) => {
        if (!isDirectory) {
            e.dataTransfer.effectAllowed = 'move'
            e.dataTransfer.setData('text/plain', fullPath)
            if (onFileDrag) {
                onFileDrag(fullPath)
            }
        }
    }

    return (
        <li style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    padding: '0.25rem 0',
                    paddingLeft: `${level * 1.25}rem`,
                    cursor: isDirectory ? 'pointer' : 'default',
                    fontSize: '0.85em',
                    color: 'var(--text-primary)',
                    userSelect: 'none',
                    borderRadius: '4px',
                    transition: 'background 0.2s'
                }}
                onClick={() => isDirectory && setIsExpanded(!isExpanded)}
                onMouseEnter={(e) => {
                    if (!isDirectory) {
                        e.currentTarget.style.background = 'var(--bg-tertiary)'
                    }
                }}
                onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent'
                }}
                draggable={!isDirectory}
                onDragStart={handleDragStart}
            >
                <span style={{ 
                    marginRight: '0.25rem', 
                    width: '0.75rem',
                    display: 'inline-block',
                    textAlign: 'center'
                }}>
                    {isDirectory ? (isExpanded ? '▾' : '▸') : ''}
                </span>
                <span style={{ marginRight: '0.5rem' }}>
                    {isDirectory ? '📁' : getFileIcon(node.name)}
                </span>
                <span style={{ 
                    opacity: isDirectory ? 1 : 0.9,
                    fontWeight: isDirectory ? 500 : 400
                }}>
                    {node.name}
                </span>
            </div>
            {isDirectory && isExpanded && hasChildren && (
                <ul style={{ margin: 0, padding: 0, marginLeft: '0.5rem' }}>
                    {node.children!.map((child, idx) => (
                        <TreeNode 
                            key={idx} 
                            node={child} 
                            level={level + 1}
                            basePath={fullPath}
                            onFileDrag={onFileDrag}
                        />
                    ))}
                </ul>
            )}
        </li>
    )
}

export default function FileTree({ folderId, onFileDrag }: Props) {
    const [tree, setTree] = useState<FileTreeNode | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const loadTree = async () => {
            if (!folderId) {
                setTree(null)
                return
            }

            setLoading(true)
            setError(null)
            try {
                if (!api || typeof api.getFolderTree !== 'function') {
                    throw new Error('API method getFolderTree is not available')
                }
                const data = await api.getFolderTree(folderId)
                console.log('File tree data received:', data)
                setTree(data)
            } catch (err) {
                const errorMessage = err instanceof Error ? err.message : 'Failed to load file tree'
                console.error('Error loading file tree:', err)
                setError(errorMessage)
            } finally {
                setLoading(false)
            }
        }

        loadTree()
    }, [folderId])

    if (!folderId) {
        return (
            <div style={{ 
                padding: '1rem', 
                color: 'var(--text-secondary)',
                textAlign: 'center',
                fontSize: '0.9em'
            }}>
                Select a project to view files
            </div>
        )
    }

    if (loading) {
        return (
            <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <span className="spinner"></span> Loading...
            </div>
        )
    }

    if (error) {
        return (
            <div style={{ padding: '1rem', color: '#dc2626', fontSize: '0.9em' }}>
                Error: {error}
            </div>
        )
    }

    if (!tree) {
        return (
            <div style={{ padding: '1rem', color: 'var(--text-secondary)', fontSize: '0.9em' }}>
                No files found
            </div>
        )
    }

    return (
        <div style={{
            padding: '0.5rem',
            fontFamily: 'monospace',
            fontSize: '0.85em',
            overflowY: 'auto',
            overflowX: 'hidden',
            height: '100%',
            flex: 1,
            minHeight: 0
        }}>
            <div style={{ 
                marginBottom: '0.5rem', 
                fontWeight: 600,
                color: 'var(--text-primary)',
                padding: '0.5rem',
                background: 'var(--bg-tertiary)',
                borderRadius: '4px',
                fontSize: '0.9em'
            }}>
                📁 {tree.name}
            </div>
            {tree.children && tree.children.length > 0 ? (
                <ul style={{ margin: 0, padding: 0 }}>
                    {tree.children.map((child, idx) => (
                        <TreeNode 
                            key={idx} 
                            node={child} 
                            level={0}
                            basePath={tree.path || tree.name}
                            onFileDrag={onFileDrag}
                        />
                    ))}
                </ul>
            ) : (
                <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic', padding: '0.5rem' }}>
                    Empty directory
                </div>
            )}
        </div>
    )
}
