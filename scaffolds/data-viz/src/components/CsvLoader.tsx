import { useState, useCallback } from "react"
import Papa from "papaparse"

interface CsvLoaderProps {
  onData: (rows: Record<string, any>[], columns: string[]) => void
}

export default function CsvLoader({ onData }: CsvLoaderProps) {
  const [dragging, setDragging] = useState(false)
  const [fileName, setFileName] = useState("")
  const [rowCount, setRowCount] = useState(0)
  const [loading, setLoading] = useState(false)

  const handleFile = useCallback((file: File) => {
    setFileName(file.name)
    setLoading(true)
    Papa.parse(file, {
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (result) => {
        const columns = result.meta.fields || []
        const rows = result.data as Record<string, any>[]
        setRowCount(rows.length)
        setLoading(false)
        onData(rows, columns)
      },
    })
  }, [onData])

  return (
    <div
      className={`csv-dropzone ${dragging ? "active" : ""}`}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => {
        e.preventDefault(); setDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) handleFile(file)
      }}
      onClick={() => {
        const input = document.createElement("input")
        input.type = "file"; input.accept = ".csv,.tsv,.txt"
        input.onchange = () => { if (input.files?.[0]) handleFile(input.files[0]) }
        input.click()
      }}
      style={{ cursor: 'pointer' }}
    >
      {loading ? (
        <div style={{ textAlign: 'center' }}>
          <div className="skeleton" style={{ width: 120, height: 12, margin: '0 auto 8px' }} />
          <span style={{ color: 'var(--text-muted, #7a7f8e)', fontSize: 'var(--text-sm, 0.875rem)' }}>
            Parsing...
          </span>
        </div>
      ) : fileName ? (
        <div style={{ textAlign: 'center' }}>
          <span style={{ fontSize: 24, display: 'block', marginBottom: 4 }}>📊</span>
          <span style={{ fontWeight: 700, color: 'var(--accent, #34d4b0)' }}>{fileName}</span>
          <span style={{
            display: 'block',
            fontSize: 'var(--text-xs, 0.75rem)',
            color: 'var(--text-muted, #7a7f8e)',
            marginTop: 4,
          }}>
            {rowCount.toLocaleString()} rows loaded — click to replace
          </span>
        </div>
      ) : (
        <div style={{ textAlign: 'center' }}>
          <span style={{ fontSize: 24, opacity: 0.4, display: 'block', marginBottom: 4 }}>
            {dragging ? '📥' : '📁'}
          </span>
          <span style={{ fontWeight: 600 }}>Drop CSV here or click to browse</span>
        </div>
      )}
    </div>
  )
}
