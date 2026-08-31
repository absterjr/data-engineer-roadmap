"""A tiny relational engine built from first principles.

Reads a CSV and supports SELECT, WHERE, JOIN, GROUP BY, ORDER BY, LIMIT,
window functions and basic aggregation — implemented by hand, with NO
SQL libraries.

Day 2 additions:
- `read_csv` now coerces strings to int/float/None where possible
- `extend` adds computed columns (SELECT expr AS name)
- `order_by` / `limit` for sorting and top-N
- aggregate functions (count, sum_, mean, min_, max_) for GROUP BY

Day 6 additions:
- window functions: `row_number`, `rank`, `dense_rank`, `running_sum`,
  `partition_sum` (SQL's ROW_NUMBER / RANK / SUM() OVER (PARTITION BY ...))
- `join` supports LEFT JOIN and uses a hash index (O(n+m) not O(n*m))
- clear errors for missing columns and missing files

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


def _require_columns(table: Table, columns, op: str) -> None:
    """Raise a clear error if any column is missing from the table."""
    missing = [c for c in columns if c not in table.columns]
    if missing:
        raise KeyError(
            f"{op}: column(s) {missing} not found in {table.name!r} "
            f"(available: {table.columns})"
        )


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
    if not path.exists():
        raise FileNotFoundError(
            f"read_csv: {path} does not exist. If this is the Online Retail "
            "dataset, get it with: python scripts/fetch_online_retail.py"
        )
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
    _require_columns(table, columns, "project")
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


def join(
    left: Table,
    right: Table,
    on_left: str,
    on_right: str,
    how: str = "inner",
) -> Table:
    """JOIN on left[on_left] == right[on_right].

    `how` is "inner" (default) or "left". A LEFT JOIN keeps every left
    row; right-side columns get None when no match exists.

    Uses a hash index on the right table, so it runs in O(n + m) instead
    of the nested loop's O(n * m) — the same trick real databases use.
    Right-side columns that already exist on the left are dropped: the
    join key is shared, so the values are equal by construction.
    """
    if how not in ("inner", "left"):
        raise ValueError(f"join: how must be 'inner' or 'left', got {how!r}")
    _require_columns(left, [on_left], "join")
    _require_columns(right, [on_right], "join")

    new_cols = [c for c in right.columns if c not in left.columns]
    columns = left.columns + new_cols

    index: dict[object, list[dict]] = {}
    for rrow in right.rows:
        index.setdefault(rrow[on_right], []).append(rrow)

    rows = []
    for lrow in left.rows:
        matches = index.get(lrow[on_left], [])
        if matches:
            for rrow in matches:
                merged = {k: v for k, v in rrow.items() if k in new_cols}
                rows.append({**lrow, **merged})
        elif how == "left":
            rows.append({**lrow, **{c: None for c in new_cols}})
    return Table(name=f"({left.name} {how}⋈ {right.name})", columns=columns, rows=rows)


def group_by(table: Table, keys: list[str], aggs) -> Table:
    """GROUP BY keys, then aggregate each group.

    aggs is either:
      - a callable (group_rows, key_values) -> dict of extra columns, or
      - a dict of output_name -> fn(group_rows, key_values) -> value.
    """
    _require_columns(table, keys, "group_by")
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
    """ORDER BY key [DESC]. Stable sort: ties keep their input order.

    NULLs sort last, whether ascending or descending.
    """
    _require_columns(table, [key], "order_by")
    rows = sorted(table.rows, key=lambda r: (r[key] is None, r[key]), reverse=desc)
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
# Window functions (SQL's OVER (PARTITION BY ... ORDER BY ...))
#
# Unlike GROUP BY, window functions do NOT collapse rows: every input row
# keeps its place, and a new column is added with the window's answer.
# Row order is preserved, exactly like SQL.
# ---------------------------------------------------------------------------


def _partition(table: Table, partition_keys: list[str]) -> dict[tuple, list[tuple[int, dict]]]:
    """Bucket (index, row) pairs by partition key. Empty key = one bucket."""
    _require_columns(table, partition_keys, "window function")
    buckets: dict[tuple, list[tuple[int, dict]]] = {}
    for i, row in enumerate(table.rows):
        key = tuple(row[k] for k in partition_keys) if partition_keys else ()
        buckets.setdefault(key, []).append((i, row))
    return buckets


def _order_partition(group, order_key: str | None, desc: bool) -> list[tuple[int, dict]]:
    """Order a partition's (index, row) pairs by order_key. NULLs last."""
    if order_key is None:
        return group
    return sorted(group, key=lambda ir: (ir[1][order_key] is None, ir[1][order_key]), reverse=desc)


def _window(table: Table, partition_keys, order_key, desc, name: str) -> list[dict]:
    """Shared plumbing: allocate the new column, preserving row order."""
    rows: list[dict | None] = [None] * len(table.rows)
    for group in _partition(table, partition_keys).values():
        ordered = _order_partition(group, order_key, desc)
        for i, row in ordered:
            r = dict(row)
            r[name] = None  # placeholder, filled by the caller
            rows[i] = r
    return rows


def row_number(
    table: Table,
    partition_keys: list[str] | None = None,
    order_key: str | None = None,
    desc: bool = False,
    name: str = "row_num",
) -> Table:
    """ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...) — 1, 2, 3..."""
    partition_keys = partition_keys or []
    _require_columns(table, [c for c in partition_keys + [order_key] if c], "row_number")
    result = _window(table, partition_keys, order_key, desc, name)
    for group in _partition(table, partition_keys).values():
        for n, (i, _) in enumerate(_order_partition(group, order_key, desc), start=1):
            result[i][name] = n
    return Table(name=table.name, columns=table.columns + [name], rows=result)


def rank(
    table: Table,
    partition_keys: list[str] | None = None,
    order_key: str | None = None,
    desc: bool = False,
    name: str = "rank",
) -> Table:
    """RANK() OVER (...): ties share a rank, then the next rank skips.

    Equal values get the same rank; the following rank is (position + 1),
    leaving gaps — exactly like SQL's RANK().
    """
    partition_keys = partition_keys or []
    _require_columns(table, [c for c in partition_keys + [order_key] if c], "rank")
    result = _window(table, partition_keys, order_key, desc, name)
    _sentinel = object()
    for group in _partition(table, partition_keys).values():
        prev, current = _sentinel, 0
        for pos, (i, row) in enumerate(_order_partition(group, order_key, desc), start=1):
            val = row[order_key]
            if prev is _sentinel or val != prev:
                current = pos
                prev = val
            result[i][name] = current
    return Table(name=table.name, columns=table.columns + [name], rows=result)


def dense_rank(
    table: Table,
    partition_keys: list[str] | None = None,
    order_key: str | None = None,
    desc: bool = False,
    name: str = "dense_rank",
) -> Table:
    """DENSE_RANK() OVER (...): ties share a rank, no gaps."""
    partition_keys = partition_keys or []
    _require_columns(table, [c for c in partition_keys + [order_key] if c], "dense_rank")
    result = _window(table, partition_keys, order_key, desc, name)
    _sentinel = object()
    for group in _partition(table, partition_keys).values():
        prev, current = _sentinel, 0
        for i, row in _order_partition(group, order_key, desc):
            val = row[order_key]
            if prev is _sentinel or val != prev:
                current += 1
                prev = val
            result[i][name] = current
    return Table(name=table.name, columns=table.columns + [name], rows=result)


def running_sum(
    table: Table,
    col: str,
    partition_keys: list[str] | None = None,
    order_key: str | None = None,
    desc: bool = False,
    name: str = "running_total",
) -> Table:
    """SUM(col) OVER (PARTITION BY ... ORDER BY ...) — running total.

    NULLs in col are treated as 0 (like SQL's default frame, which
    counts only rows seen so far).
    """
    partition_keys = partition_keys or []
    _require_columns(table, [col] + [c for c in partition_keys + [order_key] if c], "running_sum")
    result = _window(table, partition_keys, order_key, desc, name)
    for group in _partition(table, partition_keys).values():
        acc = 0.0
        for i, row in _order_partition(group, order_key, desc):
            acc += row[col] or 0
            result[i][name] = acc
    return Table(name=table.name, columns=table.columns + [name], rows=result)


def partition_sum(
    table: Table,
    col: str,
    partition_keys: list[str] | None = None,
    name: str = "partition_total",
) -> Table:
    """SUM(col) OVER (PARTITION BY ...) — the whole partition's total,
    repeated on every row. (Window without ORDER BY: frame = whole partition.)"""
    partition_keys = partition_keys or []
    _require_columns(table, [col] + partition_keys, "partition_sum")
    totals: dict[tuple, float] = {}
    for row in table.rows:
        key = tuple(row[k] for k in partition_keys) if partition_keys else ()
        totals[key] = totals.get(key, 0.0) + (row[col] or 0)
    result = _window(table, partition_keys, None, False, name)
    for row in result:
        key = tuple(row[k] for k in partition_keys) if partition_keys else ()
        row[name] = totals[key]
    return Table(name=table.name, columns=table.columns + [name], rows=result)


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