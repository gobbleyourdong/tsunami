import { useState, useMemo } from "react"

interface Column {
  key: string
  label: string
  width?: number
  editable?: boolean
}

interface DataTableProps {
  columns: Column[]
  rows: Record<string, any>[]
  editable?: boolean
  searchable?: boolean
  onCellEdit?: (rowIndex: number, key: string, value: string) => void
  highlightCell?: (rowIndex: number, key: string) => string | undefined
  onExport?: () => void
}

export default function DataTable({
  columns, rows, editable, searchable, onCellEdit, highlightCell, onExport,
}: DataTableProps) {
  const [sortKey, setSortKey] = useState("")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc")
  const [search, setSearch] = useState("")

  const filtered = useMemo(() => {
    if (!search) return rows
    const q = search.toLowerCase()
    return rows.filter(row =>
      columns.some(col => String(row[col.key] ?? "").toLowerCase().includes(q))
    )
  }, [rows, search, columns])

  const sorted = useMemo(() => {
    if (!sortKey) return filtered
    return [...filtered].sort((a, b) => {
      const av = a[sortKey] ?? "", bv = b[sortKey] ?? ""
      const cmp = typeof av === "number" ? av - (bv as number) : String(av).localeCompare(String(bv))
      return sortDir === "asc" ? cmp : -cmp
    })
  }, [filtered, sortKey, sortDir])

  const toggleSort = (key: string) => {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc")
    else { setSortKey(key); setSortDir("asc") }
  }

  return (
    <div>
      <div className="table-toolbar">
        {searchable && (
          <input placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)} style={{ maxWidth: 300 }} />
        )}
        <span className="text-muted text-sm">{sorted.length} rows</span>
        {onExport && <button onClick={onExport} className="text-sm">Export CSV</button>}
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map(col => (
                <th key={col.key} onClick={() => toggleSort(col.key)}
                    style={{ cursor: "pointer", width: col.width }}>
                  {col.label} {sortKey === col.key && (sortDir === "asc" ? "↑" : "↓")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, ri) => (
              <tr key={ri}>
                {columns.map(col => (
                  <td key={col.key}
                    contentEditable={editable || col.editable}
                    suppressContentEditableWarning
                    onBlur={e => onCellEdit?.(ri, col.key, e.currentTarget.textContent || "")}
                    style={{ background: highlightCell?.(ri, col.key) || undefined }}
                  >
                    {row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr><td colSpan={columns.length} className="text-center text-muted p-4">
                {search ? "No matches" : "No data — upload a file"}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
