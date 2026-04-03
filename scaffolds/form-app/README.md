# Form App Scaffold

Vite + React 19 + xlsx + PapaParse. File upload, spreadsheet parsing, data tables.

## Components (import from `./components`)

### FileDropzone
`<FileDropzone accept=".csv,.xlsx" onFile={file => parseFile(file).then(setSheets)} />`
- Drag-and-drop + click, shows filename after upload

### DataTable
`<DataTable columns={cols} rows={data} editable searchable onCellEdit={...} onExport={...} />`
- Sortable (click headers), searchable, editable cells, row count, export button
- highlightCell prop for conditional formatting

### parseFile
`const sheets = await parseFile(file)` → `[{columns, rows, sheetName}]`
- Parses CSV, TSV, XLS, XLSX automatically

### exportCsv
`exportCsv(columns, rows, "mydata.csv")` — triggers browser download

## CSS Classes
- `.dropzone`, `.dropzone.active` — file upload area
- `.table-scroll` — scrollable table with sticky headers
- `.table-toolbar` — search + export bar above table
- `.form-grid`, `.form-group label` — responsive form layout
- `.form-actions` — right-aligned button row
- `.steps`, `.step.active/.done` — wizard/stepper UI

## Rules
- Don't overwrite `main.tsx`, `vite.config.ts`, or `index.css`
- Use parseFile for all file imports — handles xlsx + csv
- Use exportCsv for downloads — handles quoting and encoding
