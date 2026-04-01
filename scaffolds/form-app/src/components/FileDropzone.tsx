import { useCallback, useRef, useState, DragEvent } from "react"

interface FileDropzoneProps {
  accept?: string
  onFile: (file: File) => void
  label?: string
}

/** Drag-and-drop or click file upload. */
export default function FileDropzone({
  accept = ".xlsx,.xls,.csv",
  onFile,
  label = "Drop a file here or click to upload",
}: FileDropzoneProps) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) onFile(file)
  }, [onFile])

  const handleClick = () => inputRef.current?.click()

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onFile(file)
  }

  return (
    <div
      onClick={handleClick}
      onDrop={handleDrop}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      style={{
        border: `2px dashed ${dragging ? "#0ff" : "#444"}`,
        borderRadius: 12,
        padding: 40,
        textAlign: "center",
        cursor: "pointer",
        background: dragging ? "#1a1a3a" : "#111",
        color: "#888",
        transition: "all 0.2s",
      }}
    >
      <input ref={inputRef} type="file" accept={accept} onChange={handleChange} style={{ display: "none" }} />
      <p style={{ fontSize: 16 }}>{label}</p>
      <p style={{ fontSize: 12, marginTop: 8, color: "#555" }}>Supports: {accept}</p>
    </div>
  )
}
