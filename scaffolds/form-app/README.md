# Form App Scaffold

Vite + React 19 + xlsx + PapaParse. File upload, spreadsheet parsing, data tables.
Inherits the Tsunami design system (Plus Jakarta Sans, surface hierarchy, glassmorphism).

## Components (import from `./components/ComponentName`)

| Component | Usage |
|-----------|-------|
| **FileDropzone** | `<FileDropzone accept=".csv,.xlsx" onFile={file => parseFile(file).then(setData)} maxSize={10*1024*1024} />` — Drag-and-drop + click, file type icons, size display, maxSize validation, error state |
| **DataTable** | `<DataTable columns={cols} rows={data} editable searchable onCellEdit={...} onExport={...} />` — Sort, search, edit cells, row count, export button, highlight cells |

## Utilities (import from `./components/parseFile` / `./components/exportCsv`)
- `const sheets = await parseFile(file)` → `[{columns, rows, sheetName}]` — CSV, TSV, XLS, XLSX
- `exportCsv(columns, rows, "data.csv")` — browser download with quoting

## Form CSS Classes
- `.dropzone`, `.dropzone.active` — file upload area with accent border on drag
- `.table-scroll` — scrollable table with sticky headers
- `.table-toolbar` — search + export bar above table
- `.form-grid`, `.form-group label` — responsive 2-column form layout
- `.form-actions` — right-aligned button row
- `.steps`, `.step.active/.done` — wizard/stepper UI with progress line

## Design System Classes (from base)
- `.card`, `.card.glass` — surface containers
- `button.primary`, `button.ghost`, `button.danger` — button hierarchy
- `.badge.accent`, `.badge.success`, `.badge.danger` — tag pills
- `.animate-in`, `.delay-1/2/3` — staggered entrance animations
- `.skeleton` — loading placeholder shimmer

## Hooks (import from `./hooks`)
- `useLocalStorage(key, initial)` — persist form state
- `useDebounce(value, delay)` — debounce search input

## Rules
- Don't overwrite `main.tsx`, `vite.config.ts`, or `index.css`
- Use parseFile for all file imports — handles xlsx + csv
- Use exportCsv for downloads — handles quoting and encoding
- Use CSS classes for styling — avoid inline styles
