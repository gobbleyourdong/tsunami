"""file_converter — convert between tabular formats.

Supports csv, tsv, jsonl, json, yaml. Format inferred from file
extension (override with ``--from`` / ``--to``). Each format module
defines a ``read(fh) -> Iterable[dict]`` and ``write(rows, fh)``
function; add a new format by adding a module to ``formats/``.
"""

__version__ = "0.1.0"
