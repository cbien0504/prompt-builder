import { useState } from 'react'

interface Props {
    prompts: string[]
    tokenCount: number
    onCopy?: (partIndex: number) => void
}

export default function ContextViewer({ prompts, tokenCount, onCopy }: Props) {
    const [activePart, setActivePart] = useState(0)
    const [copied, setCopied] = useState(false)
    const handleCopy = async () => {
        const text = prompts[activePart]
        if (!text) return
    
        await navigator.clipboard.writeText(text)
    
        setCopied(true)
        onCopy?.(activePart)
    
        setTimeout(() => {
            setCopied(false)
        }, 1000)
    }

    if (prompts.length === 0) return null

    return (
        <div className="card" style={{ marginBottom: '1rem' }}>
            <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                marginBottom: '0.5rem', 
                alignItems: 'center' 
            }}>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <div style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>
                        Generated Context
                    </div>
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
                <button
                    onClick={handleCopy}
                    style={{
                        fontSize: '0.85em',
                        padding: '0.2em 0.8em',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.4rem'
                    }}
                >
                    <span>
                        {prompts.length === 1
                            ? 'Copy Prompt'
                            : `Copy Part ${activePart + 1}`}
                    </span>

                    {copied && (
                        <span
                            style={{
                                color: '#16a34a',
                                fontWeight: 600,
                                fontSize: '0.9em'
                            }}
                        >
                            ✓
                        </span>
                    )}
                </button>
            </div>

            <textarea
                value={prompts[activePart] || ''}
                readOnly
                style={{
                    width: '100%',
                    height: '680px',
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

            <div style={{ 
                marginTop: '0.5rem', 
                fontSize: '0.85em', 
                color: 'var(--text-secondary)' 
            }}>
                Total Estimated Tokens: <strong>{tokenCount}</strong>
                {prompts.length > 1 && (
                    <span style={{ marginLeft: '1rem', color: '#d97706', fontWeight: 500 }}>
                        ℹ️ Split into {prompts.length} parts (Too large for one message)
                    </span>
                )}
            </div>
        </div>
    )
}