# cli/data-processor

**Pitch:** a starting template for a pipe-friendly CLI that reads record streams
(JSONL/JSON/CSV) from stdin or a file, chains operators (filter, project,
rename, count, group-by), and emits them to stdout or a file. Lineage:
`jq`, `mlr` (Miller), `csvkit` — small, composable, stream-native.

## Quick start

```bash
pip install -e .

# Filter + project + output JSONL
cat data/sample.jsonl \
  | data-processor process --filter 'status==active' --select id,user.name,score

# Group-count by nested field
data-processor count -i data/sample.jsonl --group-by user.city
```

## Operators included

| Operator     | CLI flag                        | Use                                       |
|--------------|---------------------------------|-------------------------------------------|
| `filter_op`  | `--filter 'field OP value'`     | Keep records where predicate holds        |
| `project`    | `--select a,b,c`                | Keep only these fields (dotted paths)     |
| `map_rename` | `--rename old=new`              | Rename a field                            |
| `count`      | `count`                         | Emit `{"count": N}`                       |
| `group_count`| `count --group-by field`        | Emit one record per group with `count`    |

Predicate operators: `==`, `!=`, `>`, `>=`, `<`, `<=`. Dotted paths descend
nested records (`user.name`, `address.city`).

## Customize

- **Add a new operator** → write a generator in `src/data_processor/operators.py`
  that takes `Iterable[Record]` and yields `Record`s. Wire it into a new Click
  command or flag in `cli.py`.
- **Add a new format** → extend `read_records` / `write_records` in `io.py`.
  The `auto` sniffer only looks at the first non-whitespace character.
- **Streaming discipline:** keep operators lazy (generators, not lists).
  The scaffold assumes pipe inputs may be unbounded.

## Test

The canary lives in the repo-root at `tests/scaffolds/data-processor/canary.test.py`.
Run it with `pytest tests/scaffolds/data-processor/` — it installs the scaffold
in a temp venv, pipes the sample fixture through, and asserts shape.

## Anchors

`jq`, `mlr`, `csvkit`, `xsv`, `json-lines`, `ripgrep` (as output consumer).
