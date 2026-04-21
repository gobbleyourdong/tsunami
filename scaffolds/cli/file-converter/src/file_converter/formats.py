"""Format readers + writers.

Each format is a (reader, writer) pair keyed by short name. Readers
accept a text stream + return an iterator of dicts. Writers accept
an iterable of dicts + a text stream. Add a new format by defining
the two functions and registering them in ``REGISTRY``.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Callable, Iterable, Iterator, TextIO

import yaml


Record = dict[str, object]
Reader = Callable[[TextIO], Iterator[Record]]
Writer = Callable[[Iterable[Record], TextIO], None]


def read_csv(fh: TextIO) -> Iterator[Record]:
    return (dict(row) for row in csv.DictReader(fh))


def write_csv(rows: Iterable[Record], fh: TextIO) -> None:
    rows = list(rows)
    if not rows:
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)


def read_tsv(fh: TextIO) -> Iterator[Record]:
    return (dict(row) for row in csv.DictReader(fh, delimiter="\t"))


def write_tsv(rows: Iterable[Record], fh: TextIO) -> None:
    rows = list(rows)
    if not rows:
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
    writer.writeheader()
    writer.writerows(rows)


def read_jsonl(fh: TextIO) -> Iterator[Record]:
    for line in fh:
        line = line.strip()
        if line:
            yield json.loads(line)


def write_jsonl(rows: Iterable[Record], fh: TextIO) -> None:
    for r in rows:
        fh.write(json.dumps(r, separators=(",", ":"), sort_keys=True))
        fh.write("\n")


def read_json(fh: TextIO) -> Iterator[Record]:
    data = json.load(fh)
    if isinstance(data, list):
        return iter(data)
    return iter([data])


def write_json(rows: Iterable[Record], fh: TextIO) -> None:
    json.dump(list(rows), fh, indent=2, sort_keys=True)
    fh.write("\n")


def read_yaml(fh: TextIO) -> Iterator[Record]:
    data = yaml.safe_load(fh)
    if isinstance(data, list):
        return iter(data)
    if isinstance(data, dict):
        return iter([data])
    return iter(())


def write_yaml(rows: Iterable[Record], fh: TextIO) -> None:
    yaml.safe_dump(list(rows), fh, sort_keys=True)


REGISTRY: dict[str, tuple[Reader, Writer]] = {
    "csv":   (read_csv,   write_csv),
    "tsv":   (read_tsv,   write_tsv),
    "jsonl": (read_jsonl, write_jsonl),
    "json":  (read_json,  write_json),
    "yaml":  (read_yaml,  write_yaml),
    "yml":   (read_yaml,  write_yaml),
}


def infer(path: str) -> str:
    """Return the format name for a filename, based on its extension."""
    if "." not in path:
        return ""
    ext = path.rsplit(".", 1)[-1].lower()
    return ext if ext in REGISTRY else ""
