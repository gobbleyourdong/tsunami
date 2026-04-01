interface Column {
  key: string
  label: string
  width?: number
}

interface DataTableProps {
  columns: Column[]
  rows: Record<string, any>[]
  onRowClick?: (row: Record<string, any>) => void
}

/** Sortable data table — pass columns + rows, get a table. */
export default function DataTable({ columns, rows, onRowClick }: DataTableProps) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key} style={{
                textAlign: "left", padding: "10px 12px",
                borderBottom: "1px solid #2a2a4a",
                color: "#888", fontSize: 12, textTransform: "uppercase",
                width: col.width,
              }}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              onClick={() => onRowClick?.(row)}
              style={{ cursor: onRowClick ? "pointer" : "default" }}
              onMouseEnter={e => (e.currentTarget.style.background = "#1f1f36")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              {columns.map(col => (
                <td key={col.key} style={{ padding: "10px 12px", borderBottom: "1px solid #1a1a2e" }}>
                  {row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
