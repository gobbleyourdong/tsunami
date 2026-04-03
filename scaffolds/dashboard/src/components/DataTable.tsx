import { useState, useMemo } from "react"

interface Column {
  key: string
  label: string
  width?: number
  sortable?: boolean
  render?: (value: any, row: Record<string, any>) => React.ReactNode
}

interface DataTableProps {
  columns: Column[]
  rows: Record<string, any>[]
  onRowClick?: (row: Record<string, any>) => void
  searchable?: boolean
}

export default function DataTable({ columns, rows, onRowClick, searchable }: DataTableProps) {
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
      {searchable && (
        <input
          placeholder="Search..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="mb-4"
          style={{ maxWidth: 300 }}
        />
      )}
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              {columns.map(col => (
                <th
                  key={col.key}
                  onClick={col.sortable !== false ? () => toggleSort(col.key) : undefined}
                  style={{ cursor: col.sortable !== false ? "pointer" : "default", width: col.width }}
                >
                  {col.label}
                  {sortKey === col.key && (sortDir === "asc" ? " ↑" : " ↓")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <tr key={i} onClick={() => onRowClick?.(row)} style={{ cursor: onRowClick ? "pointer" : "default" }}>
                {columns.map(col => (
                  <td key={col.key}>
                    {col.render ? col.render(row[col.key], row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr><td colSpan={columns.length} className="text-center text-muted p-4">No data</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
