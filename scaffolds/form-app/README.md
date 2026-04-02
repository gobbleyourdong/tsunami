# Form App Template

React 19 + TypeScript + Vite + xlsx + papaparse. For apps with file uploads and editable data.

## Pre-built Components

Import from `./components`:
- `FileDropzone` — drag-and-drop file upload (accepts .xlsx, .xls, .csv)
- `DataTable` — editable table with sticky headers and cell highlighting
- `parseFile(file)` — parses xlsx/xls/csv into `{ columns, rows, sheetName }[]`

## Build Loop

1. Write types in `src/types.ts`
2. Import `FileDropzone`, `DataTable`, `parseFile` from `./components`
3. Write domain logic (diff tracking, validation, transforms)
4. Wire everything in `src/App.tsx`
5. `npx vite build` to compile-check

## Usage Examples

```tsx
import { FileDropzone, DataTable, parseFile } from "./components"

// Upload and parse
<FileDropzone onFile={async (file) => {
  const sheets = await parseFile(file)
  setData(sheets[0])
}} />

// Display editable table
<DataTable
  columns={data.columns}
  rows={data.rows}
  editable={true}
  onCellEdit={(row, key, value) => trackChange(row, key, value)}
  highlightCell={(row, key) => hasChanged(row, key) ? "#2a1a00" : undefined}
/>
```

## File Structure

```
src/
  App.tsx           ← Wire your app here
  types.ts          ← Your domain interfaces
  components/
    FileDropzone.tsx ← Drag-drop upload (ready to use)
    DataTable.tsx    ← Editable table (ready to use)
    parseFile.ts     ← xlsx/csv parser (ready to use)
    index.ts         ← Barrel exports
```
