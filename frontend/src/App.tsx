import { useState, useEffect } from 'react'
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

    const loadFolders = async () => {
        setLoading(true)
        try {
            const data = await api.getFolders()
            setFolders(data)
            
            // Auto-select if only one folder
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
                    <div style={{ fontSize: '0.85em', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                        File Tree
                    </div>
                    <div style={{ 
                        flex: 1, 
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column',
                        minHeight: 0
                    }}>
                        <FileTree folderId={activeFolderId} onFileDrag={handleFileDrag} />
                    </div>
                </div>
            </div>
            <div className="main-content">
                <SearchBar activeFolderId={activeFolderId} />
            </div>
        </div>
    )
}

export default App
