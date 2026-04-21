"""Format-detecting stream IO.

Read: JSONL (one object per line), JSON array, or CSV. Auto-detects
from content sniff rather than filename so `--input -` (stdin) works.

Write: JSONL, JSON array, CSV, or plain. Writer never closes stdout;
caller owns the file handle lifetime.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from typing import Iterable, Iterator


Record = dict[str, object]


def _open_read(path: str):
    if path == "-" or path == "":
        return sys.stdin
    return open(path, "r", encoding="utf-8", newline="")


def _open_write(path: str):
    if path == "-" or path == "":
        return sys.stdout
    return open(path, "w", encoding="utf-8", newline="")


def _sniff_format(head: str) -> str:
    stripped = head.lstrip()
    if not stripped:
        return "jsonl"
    if stripped[0] == "[":
        return "json"
    if stripped[0] == "{":
        return "jsonl"
    return "csv"


def read_records(path: str, fmt: str = "auto") -> Iterator[Record]:
    fh = _open_read(path)
    try:
        text = fh.read()
    finally:
        if fh is not sys.stdin:
            fh.close()

    if not text.strip():
        return iter(())

    actual = fmt
    if fmt == "auto":
        actual = _sniff_format(text[:512])

    if actual == "jsonl":
        return (json.loads(line) for line in text.splitlines() if line.strip())
    if actual == "json":
        data = json.loads(text)
        if isinstance(data, list):
            return iter(data)
        return iter([data])
    if actual == "csv":
        reader = csv.DictReader(io.StringIO(text))
        return (dict(row) for row in reader)
    raise ValueError(f"unknown input format: {actual!r}")


def write_records(records: Iterable[Record], path: str, fmt: str = "jsonl") -> int:
    fh = _open_write(path)
    count = 0
    try:
        if fmt == "jsonl":
            for r in records:
                fh.write(json.dumps(r, separators=(",", ":"), sort_keys=True))
                fh.write("\n")
                count += 1
        elif fmt == "json":
            rows = list(records)
            count = len(rows)
            json.dump(rows, fh, separators=(",", ":"), sort_keys=True)
            fh.write("\n")
        elif fmt == "csv":
            rows = list(records)
            count = len(rows)
            if rows:
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
        elif fmt == "plain":
            for r in records:
                fh.write(" ".join(str(v) for v in r.values()))
                fh.write("\n")
                count += 1
        else:
            raise ValueError(f"unknown output format: {fmt!r}")
    finally:
        if fh is not sys.stdout:
            fh.close()
    return count
