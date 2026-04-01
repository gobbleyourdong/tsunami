import * as XLSX from "xlsx"
import Papa from "papaparse"

export interface ParsedSheet {
  columns: { key: string; label: string }[]
  rows: Record<string, any>[]
  sheetName: string
}

/** Parse xlsx, xls, or csv into columns + rows. */
export async function parseFile(file: File): Promise<ParsedSheet[]> {
  const ext = file.name.split(".").pop()?.toLowerCase()

  if (ext === "csv") {
    return new Promise(resolve => {
      Papa.parse(file, {
        header: true,
        complete: result => {
          const cols = (result.meta.fields || []).map(f => ({ key: f, label: f }))
          resolve([{ columns: cols, rows: result.data as Record<string, any>[], sheetName: "Sheet1" }])
        },
      })
    })
  }

  // xlsx / xls
  const data = await file.arrayBuffer()
  const wb = XLSX.read(data, { type: "array" })
  return wb.SheetNames.map(name => {
    const ws = wb.Sheets[name]
    const json = XLSX.utils.sheet_to_json<Record<string, any>>(ws)
    const cols = json.length > 0
      ? Object.keys(json[0]).map(k => ({ key: k, label: k }))
      : []
    return { columns: cols, rows: json, sheetName: name }
  })
}
