import { useCallback, useRef, useState, DragEvent } from "react"

interface FileDropzoneProps {
  accept?: string
  onFile: (file: File) => void
  label?: string
  multiple?: boolean
}

export default function FileDropzone({
  accept = ".xlsx,.xls,.csv,.json,.tsv",
  onFile,
  label = "Drop a file here or click to upload",
  multiple = false,
}: FileDropzoneProps) {
  const [dragging, setDragging] = useState(false)
  const [fileName, setFileName] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) { onFile(file); setFileName(file.name) }
  }, [onFile])

  return (
    <div
      className={`dropzone ${dragging ? "active" : ""}`}
      onClick={() => inputRef.current?.click()}
      onDrop={handleDrop}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
    >
      <input ref={inputRef} type="file" accept={accept} multiple={multiple}
        onChange={e => { const f = e.target.files?.[0]; if (f) { onFile(f); setFileName(f.name) } }}
        style={{ display: "none" }} />
      {fileName
        ? <><span className="text-accent text-bold">{fileName}</span><br/><span className="text-sm text-muted">Click to replace</span></>
        : <><p>{label}</p><p className="text-sm text-muted mt-2">Supports: {accept}</p></>
      }
    </div>
  )
}
