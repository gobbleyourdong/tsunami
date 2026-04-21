"""data_processor — pipe-friendly record transformer.

Reads JSONL/CSV from stdin or a file, applies an ordered chain of
operators (filter, map, project, count), and emits JSONL/CSV/plain
to stdout or a file. A thin scaffold — add domain operators in
:mod:`data_processor.operators`, wire them into the CLI in
:mod:`data_processor.cli`.
"""

__version__ = "0.1.0"
