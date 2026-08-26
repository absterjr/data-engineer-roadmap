"""A tiny relational engine built from first principles.

Reads a CSV and supports SELECT, WHERE, JOIN, GROUP BY, ORDER BY, LIMIT
and basic aggregation — implemented by hand, with NO SQL libraries.

Day 2 additions:
- `read_csv` now coerces strings to int/float/None where possible
- `extend` adds computed columns (SELECT expr AS name)
- `order_by` / `limit` for sorting and top-N
- aggregate functions (count, sum_, mean, min_, max_) for GROUP BY

These are the building blocks you'd otherwise take for granted in SQL.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Core table
# ---------------------------------------------------------------------------


@dataclass
class Table:
    """An in-memory table: a list of column names and a list of rows."""

    name: str
    columns: list[str]
    rows: list[dict] = field(default_factory=list)

    @property
    def width(self) -> int:
        return len(self.columns)

    def __len__(self) -> int:
        return len(self.rows)

    def __repr__(self) -> str:
        return f"Table({self.name!r}, cols={self.columns}, rows={len(self.rows)})"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _coerce(value: str):
    """Best-effort cast of a CSV string to int / float / None / str.

    This mirrors what a database does when it infers a column type:
    '' and NaN-ish strings become NULL, numeric-looking strings become
    numbers. '17850.0' becomes the int 17850, not a float.
    """
    v = value.strip()
    if v in ("", "nan", "NA", "N/A", "NULL", "null", "None"):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except ValueError:
        return v


def read_csv(path: str | Path, name: str | None = None, coerce: bool = True) -> Table:
    """Read a CSV file into a Table. Assume the first row is a header."""
    path = Path(path)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        if coerce:
            rows = [{k: _coerce(v) for k, v in row.items()} for row in reader]
        else:
            rows = [dict(row) for row in reader]
    return Table(name=name or path.stem, columns=columns, rows=rows)


# ---------------------------------------------------------------------------
# Relational operations
# ---------------------------------------------------------------------------


def project(table: Table, columns: list[str]) -> Table:
    """SELECT: keep only the given columns (in that order)."""
    return Table(
        name=table.name,
        columns=columns,
        rows=[{c: row[c] for c in columns} for row in table.rows],
    )


def where(table: Table, predicate: Callable[[dict], bool]) -> Table:
    """Filter rows where predicate(row) is True."""
    return Table(
        name=table.name,
        columns=table.columns,
        rows=[row for row in table.rows if predicate(row)],
    )


def extend(table: Table, expr: Callable[[dict], object], name: str) -> Table:
    """SELECT expr AS name — add a computed column."""
    rows = []
    for row in table.rows:
        new_row = dict(row)
        new_row[name] = expr(new_row)
        rows.append(new_row)
    return Table(name=table.name, columns=table.columns + [name], rows=rows)


def join(left: Table, right: Table, on_left: str, on_right: str) -> Table:
    """INNER JOIN on left[on_left] == right[on_right].

    Right-side columns that already exist on the left are dropped: the
    join key is shared, so the values are equal by construction.
    """
    new_cols = [c for c in right.columns if c not in left.columns]
    columns = left.columns + new_cols
    rows = []
    for lrow in left.rows:
        for rrow in right.rows:
            if lrow[on_left] == rrow[on_right]:
                merged = {k: v for k, v in rrow.items() if k in new_cols}
                rows.append({**lrow, **merged})
    return Table(name=f"({left.name} ⋈ {right.name})", columns=columns, rows=rows)


def group_by(table: Table, keys: list[str], aggs) -> Table:
    """GROUP BY keys, then aggregate each group.

    aggs is either:
      - a callable (group_rows, key_values) -> dict of extra columns, or
      - a dict of output_name -> fn(group_rows, key_values) -> value.
    """
    buckets: dict[tuple, list[dict]] = {}
    for row in table.rows:
        key = tuple(row[k] for k in keys)
        buckets.setdefault(key, []).append(row)

    rows = []
    for key, group in buckets.items():
        base = dict(zip(keys, key))
        if callable(aggs):
            base.update(aggs(group, key))
        else:
            for name, fn in aggs.items():
                base[name] = fn(group, key)
        rows.append(base)

    columns = keys
    if rows:
        columns = columns + [c for c in rows[0] if c not in keys]

    return Table(name=f"grouped({table.name})", columns=columns, rows=rows)


def order_by(table: Table, key: str, desc: bool = False) -> Table:
    """ORDER BY key [DESC]. Stable sort: ties keep their input order."""
    rows = sorted(table.rows, key=lambda r: r[key], reverse=desc)
    return Table(name=table.name, columns=table.columns, rows=rows)


def limit(table: Table, n: int) -> Table:
    """LIMIT n — keep only the first n rows."""
    return Table(name=table.name, columns=table.columns, rows=table.rows[:n])


# ---------------------------------------------------------------------------
# Aggregates (for use with group_by)
# ---------------------------------------------------------------------------


def count(rows: list[dict], key=None) -> int:
    """COUNT(*) — number of rows in the group."""
    return len(rows)


def sum_(col: str) -> Callable[[list[dict], tuple], float]:
    """SUM(col) — sum over a column, ignoring NULLs (like SQL)."""

    def agg(rows: list[dict], key=None) -> float:
        return sum(r[col] for r in rows if r[col] is not None)

    return agg


def mean(col: str) -> Callable[[list[dict], tuple], float | None]:
    """AVG(col) — mean of a column, ignoring NULLs."""

    def agg(rows: list[dict], key=None) -> float | None:
        vals = [r[col] for r in rows if r[col] is not None]
        return sum(vals) / len(vals) if vals else None

    return agg


def min_(col: str) -> Callable[[list[dict], tuple], object]:
    """MIN(col)."""

    def agg(rows: list[dict], key=None):
        vals = [r[col] for r in rows if r[col] is not None]
        return min(vals) if vals else None

    return agg


def max_(col: str) -> Callable[[list[dict], tuple], object]:
    """MAX(col)."""

    def agg(rows: list[dict], key=None):
        vals = [r[col] for r in rows if r[col] is not None]
        return max(vals) if vals else None

    return agg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print("usage: python engine.py path/to/data.csv")
        return

    t = read_csv(sys.argv[1])
    print(t)
    print("Preview:")
    for row in t.rows[:5]:
        print(row)


if __name__ == "__main__":
    main()