import { useCallback, useRef, useState, DragEvent } from "react"

interface FileDropzoneProps {
  accept?: string
  onFile: (file: File) => void
  label?: string
  multiple?: boolean
  maxSize?: number  // bytes
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const fileIcon = (name: string) => {
  const ext = name.split('.').pop()?.toLowerCase()
  if (ext === 'csv' || ext === 'tsv') return '📊'
  if (ext === 'xlsx' || ext === 'xls') return '📗'
  if (ext === 'json') return '📋'
  if (ext === 'pdf') return '📕'
  if (ext?.match(/^(png|jpg|jpeg|gif|svg|webp)$/)) return '🖼'
  return '📄'
}

export default function FileDropzone({
  accept = ".xlsx,.xls,.csv,.json,.tsv",
  onFile,
  label = "Drop a file here or click to upload",
  multiple = false,
  maxSize,
}: FileDropzoneProps) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<{ name: string; size: number } | null>(null)
  const [error, setError] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  const processFile = useCallback((f: File) => {
    setError("")
    if (maxSize && f.size > maxSize) {
      setError(`File too large (${formatSize(f.size)}). Max: ${formatSize(maxSize)}`)
      return
    }
    setFile({ name: f.name, size: f.size })
    onFile(f)
  }, [onFile, maxSize])

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) processFile(f)
  }, [processFile])

  return (
    <div
      className={`dropzone ${dragging ? "active" : ""}`}
      onClick={() => inputRef.current?.click()}
      onDrop={handleDrop}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      style={{ cursor: 'pointer' }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={e => {
          const f = e.target.files?.[0]
          if (f) processFile(f)
        }}
        style={{ display: "none" }}
      />
      {error ? (
        <div style={{ color: 'var(--danger, #f06060)', textAlign: 'center' }}>
          <p style={{ fontWeight: 600 }}>{error}</p>
          <p className="text-sm text-muted" style={{ marginTop: 6 }}>Click to try again</p>
        </div>
      ) : file ? (
        <div style={{ textAlign: 'center' }}>
          <span style={{ fontSize: 28 }}>{fileIcon(file.name)}</span>
          <p style={{ fontWeight: 700, color: 'var(--accent, #34d4b0)', marginTop: 6 }}>{file.name}</p>
          <p style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-muted, #7a7f8e)', marginTop: 2 }}>
            {formatSize(file.size)} — Click to replace
          </p>
        </div>
      ) : (
        <div style={{ textAlign: 'center' }}>
          <span style={{ fontSize: 28, opacity: 0.4, display: 'block', marginBottom: 8 }}>
            {dragging ? '📥' : '📁'}
          </span>
          <p style={{ fontWeight: 600 }}>{label}</p>
          <p style={{ fontSize: 'var(--text-xs, 0.75rem)', color: 'var(--text-dim, #4a4f5e)', marginTop: 6 }}>
            Supports: {accept}
          </p>
        </div>
      )}
    </div>
  )
}
