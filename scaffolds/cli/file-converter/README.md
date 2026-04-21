# cli/file-converter

**Pitch:** converts tabular data between csv / tsv / jsonl / json / yaml. Format
inferred from file extension; override with `--from` / `--to`. Lineage:
`csvkit`, `yq`, `dasel`, `jq` — one-shot transforms, not pipelines.

## Quick start

```bash
pip install -e .

file-converter -i data/sample.csv -o out.jsonl
file-converter -i data/sample.jsonl -o out.yaml
file-converter --from csv --to json -i data/sample.csv -o -    # write json to stdout
cat data/sample.csv | file-converter --from csv --to jsonl     # full pipe
```

## Formats included

| Format | Reader      | Writer       | Notes                                              |
|--------|-------------|--------------|----------------------------------------------------|
| csv    | DictReader  | DictWriter   | Headers required; values are strings               |
| tsv    | DictReader  | DictWriter   | Tab-delimited variant                              |
| jsonl  | line→json   | json.dumps   | One object per line                                |
| json   | json.load   | json.dump    | Array of objects (or single object → list of 1)    |
| yaml   | yaml.safe_load | yaml.safe_dump | Array or mapping                                   |

## Customize

- **Add a new format** → define `read_<fmt>(fh)` + `write_<fmt>(rows, fh)` in
  `src/file_converter/formats.py`, register the pair in `REGISTRY`.
- **Type coercion** → CSV/TSV values come in as strings; add a `--coerce` flag
  that runs a `try: int → float → bool → str` ladder per field.
- **Streaming** → writers currently materialize the full list for json/yaml
  (unavoidable given both formats need the outer array). csv/tsv/jsonl can
  stream; if you need that, split writer into chunked vs whole.

## Test

`pytest tests/scaffolds/file-converter/` — invokes the scaffold via
`python -m file_converter`, pipes fixtures through, asserts each
format round-trips structurally.

## Anchors

`csvkit`, `yq`, `dasel`, `jq`, `miller`.
