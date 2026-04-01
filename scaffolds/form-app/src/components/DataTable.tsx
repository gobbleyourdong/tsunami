interface Column {
  key: string
  label: string
}

interface DataTableProps {
  columns: Column[]
  rows: Record<string, any>[]
  editable?: boolean
  onCellEdit?: (rowIndex: number, key: string, value: string) => void
  highlightCell?: (rowIndex: number, key: string) => string | undefined
}

/** Editable data table — pass columns + rows, optionally edit cells. */
export default function DataTable({
  columns, rows, editable = false, onCellEdit, highlightCell,
}: DataTableProps) {
  return (
    <div style={{ overflowX: "auto", maxHeight: "60vh", overflowY: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key} style={{
                textAlign: "left", padding: "8px 10px",
                borderBottom: "2px solid #333", color: "#888",
                fontSize: 11, textTransform: "uppercase",
                position: "sticky", top: 0, background: "#111",
              }}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {columns.map(col => {
                const bg = highlightCell?.(ri, col.key)
                return (
                  <td
                    key={col.key}
                    contentEditable={editable}
                    suppressContentEditableWarning
                    onBlur={e => onCellEdit?.(ri, col.key, e.currentTarget.textContent || "")}
                    style={{
                      padding: "6px 10px",
                      borderBottom: "1px solid #1a1a1a",
                      background: bg || "transparent",
                      outline: "none",
                    }}
                  >
                    {row[col.key]}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
