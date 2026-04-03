import { useState, useCallback } from "react"

interface FileNode {
  name: string
  type: "file" | "folder"
  children?: FileNode[]
  size?: number
}

interface FileManagerProps {
  files: FileNode[]
  onSelect?: (path: string) => void
  onRename?: (oldPath: string, newPath: string) => void
  onDelete?: (path: string) => void
  onUpload?: (files: FileList) => void
}

function FileTree({ node, path, depth, onSelect, onRename, onDelete }: {
  node: FileNode; path: string; depth: number
  onSelect?: (p: string) => void; onRename?: (o: string, n: string) => void; onDelete?: (p: string) => void
}) {
  const [expanded, setExpanded] = useState(depth < 1)
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState(node.name)
  const fullPath = path ? `${path}/${node.name}` : node.name

  const handleRename = () => {
    if (editName && editName !== node.name) onRename?.(fullPath, `${path}/${editName}`)
    setEditing(false)
  }

  const icon = node.type === "folder" ? (expanded ? "📂" : "📁") : "📄"

  return (
    <div>
      <div
        onClick={() => node.type === "folder" ? setExpanded(!expanded) : onSelect?.(fullPath)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '4px 8px', paddingLeft: depth * 16 + 8,
          cursor: 'pointer', fontSize: 13, borderRadius: 4,
          color: 'var(--text-primary, #e2e8f0)',
          transition: 'background 100ms',
        }}
        onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-tertiary, #1a2332)')}
        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
      >
        <span style={{ fontSize: 14 }}>{icon}</span>
        {editing ? (
          <input
            value={editName}
            onChange={e => setEditName(e.target.value)}
            onBlur={handleRename}
            onKeyDown={e => e.key === "Enter" && handleRename()}
            autoFocus
            onClick={e => e.stopPropagation()}
            style={{
              background: 'var(--bg-primary, #0a0e17)', border: '1px solid var(--accent, #4a9eff)',
              color: 'var(--text-primary, #e2e8f0)', borderRadius: 4, padding: '1px 4px', fontSize: 13,
            }}
          />
        ) : (
          <span style={{ flex: 1 }}>{node.name}</span>
        )}
        {node.size != null && <span style={{ color: 'var(--text-dim, #4a4f5e)', fontSize: 11 }}>{(node.size / 1024).toFixed(1)}K</span>}
        <span
          onClick={e => { e.stopPropagation(); setEditing(true) }}
          style={{ opacity: 0.4, cursor: 'pointer', fontSize: 11 }}
          title="Rename"
        >✏️</span>
        <span
          onClick={e => { e.stopPropagation(); onDelete?.(fullPath) }}
          style={{ opacity: 0.4, cursor: 'pointer', fontSize: 11 }}
          title="Delete"
        >🗑️</span>
      </div>
      {expanded && node.children?.map((child, i) => (
        <FileTree key={i} node={child} path={fullPath} depth={depth + 1} onSelect={onSelect} onRename={onRename} onDelete={onDelete} />
      ))}
    </div>
  )
}

export default function FileManager({ files, onSelect, onRename, onDelete, onUpload }: FileManagerProps) {
  const [dragOver, setDragOver] = useState(false)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false)
    if (e.dataTransfer.files.length) onUpload?.(e.dataTransfer.files)
  }, [onUpload])

  return (
    <div style={{
      border: '1px solid var(--border, rgba(255,255,255,0.08))',
      borderRadius: 'var(--radius-md, 8px)',
      background: 'var(--bg-secondary, #111827)',
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '8px 12px', borderBottom: '1px solid var(--border, rgba(255,255,255,0.08))',
        background: 'var(--bg-tertiary, #1a2332)',
        fontSize: 12, fontWeight: 600, color: 'var(--text-secondary, #94a3b8)',
        textTransform: 'uppercase', letterSpacing: '0.05em',
      }}>
        Files
      </div>
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        style={{
          padding: 4, minHeight: 200,
          background: dragOver ? 'rgba(74, 158, 255, 0.05)' : 'transparent',
          transition: 'background 150ms',
        }}
      >
        {files.map((node, i) => (
          <FileTree key={i} node={node} path="" depth={0} onSelect={onSelect} onRename={onRename} onDelete={onDelete} />
        ))}
        {files.length === 0 && (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-dim, #4a4f5e)', fontSize: 13 }}>
            Drop files here or add files to get started
          </div>
        )}
      </div>
    </div>
  )
}
