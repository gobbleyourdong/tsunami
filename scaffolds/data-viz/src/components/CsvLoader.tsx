import { useState, useCallback } from "react"
import Papa from "papaparse"

interface CsvLoaderProps {
  onData: (rows: Record<string, any>[], columns: string[]) => void
}

/** Drag-and-drop CSV file loader. Parses with papaparse. */
export default function CsvLoader({ onData }: CsvLoaderProps) {
  const [dragging, setDragging] = useState(false)
  const [fileName, setFileName] = useState("")

  const handleFile = useCallback((file: File) => {
    setFileName(file.name)
    Papa.parse(file, {
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (result) => {
        const columns = result.meta.fields || []
        onData(result.data as Record<string, any>[], columns)
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
    >
      {fileName
        ? <span className="text-accent">{fileName}</span>
        : <span>Drop CSV here or click to browse</span>
      }
    </div>
  )
}
