/** Export rows to CSV and trigger download */
export function exportCsv(columns: { key: string; label: string }[], rows: Record<string, any>[], filename = "export.csv") {
  const header = columns.map(c => c.label).join(",")
  const body = rows.map(row =>
    columns.map(c => {
      const val = String(row[c.key] ?? "")
      return val.includes(",") || val.includes('"') ? `"${val.replace(/"/g, '""')}"` : val
    }).join(",")
  ).join("\n")
  const blob = new Blob([header + "\n" + body], { type: "text/csv" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}
