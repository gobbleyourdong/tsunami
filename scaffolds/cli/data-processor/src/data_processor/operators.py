"""Operator primitives.

Each operator takes an iterable of records and returns an iterable of
records. Chain them in :mod:`data_processor.cli`. Add domain operators
here — keep them streaming (yield, don't list) so piping arbitrary-
size inputs stays bounded in memory.
"""
from __future__ import annotations

import operator
from typing import Callable, Iterable, Iterator

Record = dict[str, object]
Predicate = Callable[[Record], bool]


_CMP = {
    "==": operator.eq,
    "!=": operator.ne,
    ">":  operator.gt,
    ">=": operator.ge,
    "<":  operator.lt,
    "<=": operator.le,
}


def _coerce(a: object, b: str) -> tuple[object, object]:
    """Make comparisons work across JSON types without surprising users.

    If the record value is numeric, try parsing the rhs the same way.
    """
    if isinstance(a, bool):
        return a, b.lower() in ("true", "1", "yes")
    if isinstance(a, (int, float)):
        try:
            return a, float(b) if "." in b else int(b)
        except ValueError:
            return a, b
    return a, b


def parse_predicate(expr: str) -> Predicate:
    """Parse a simple `field OP value` expression.

    Supports ==, !=, >, >=, <, <=. Dotted field paths descend nested
    records (``user.name``).
    """
    for sym in (">=", "<=", "==", "!=", ">", "<"):
        if sym in expr:
            lhs, rhs = expr.split(sym, 1)
            lhs = lhs.strip()
            rhs = rhs.strip()
            op = _CMP[sym]

            def pred(r: Record, _lhs=lhs, _rhs=rhs, _op=op) -> bool:
                val = _get_path(r, _lhs)
                a, b = _coerce(val, _rhs)
                try:
                    return bool(_op(a, b))
                except TypeError:
                    return False
            return pred
    raise ValueError(f"predicate needs a comparison operator: {expr!r}")


def _get_path(r: Record, path: str) -> object:
    cur: object = r
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def filter_op(records: Iterable[Record], pred: Predicate) -> Iterator[Record]:
    for r in records:
        if pred(r):
            yield r


def project(records: Iterable[Record], fields: list[str]) -> Iterator[Record]:
    for r in records:
        yield {f: _get_path(r, f) for f in fields}


def map_rename(records: Iterable[Record], renames: dict[str, str]) -> Iterator[Record]:
    for r in records:
        yield {renames.get(k, k): v for k, v in r.items()}


def count(records: Iterable[Record]) -> Iterator[Record]:
    n = sum(1 for _ in records)
    yield {"count": n}


def group_count(records: Iterable[Record], key: str) -> Iterator[Record]:
    buckets: dict[object, int] = {}
    for r in records:
        k = _get_path(r, key)
        buckets[k] = buckets.get(k, 0) + 1
    for k, v in buckets.items():
        yield {key: k, "count": v}
