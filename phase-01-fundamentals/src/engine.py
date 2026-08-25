"""A tiny relational engine built from first principles.

Reads a CSV and supports SELECT, WHERE, JOIN, GROUP BY and basic
aggregation — implemented by hand, with NO SQL libraries.

These are the building blocks you'll implement yourself, one at a time.
See the README for the full phase write-up.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


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


def read_csv(path: str | Path, name: str | None = None) -> Table:
    """Read a CSV file into a Table. Assume the first row is a header."""
    path = Path(path)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return Table(name=name or path.stem, columns=columns, rows=rows)


def project(table: Table, columns: list[str]) -> Table:
    """SELECT: keep only the given columns (in that order)."""
    return Table(
        name=table.name,
        columns=columns,
        rows=[{c: row[c] for c in columns} for row in table.rows],
    )


def where(table: Table, predicate) -> Table:
    """Filter rows where predicate(row) is True."""
    return Table(
        name=table.name,
        columns=table.columns,
        rows=[row for row in table.rows if predicate(row)],
    )


def join(left: Table, right: Table, on_left: str, on_right: str) -> Table:
    """INNER JOIN on left[on_left] == right[on_right]."""
    columns = left.columns + right.columns
    rows = []
    for lrow in left.rows:
        for rrow in right.rows:
            if lrow[on_left] == rrow[on_right]:
                rows.append({**lrow, **rrow})
    return Table(name=f"({left.name} ⋈ {right.name})", columns=columns, rows=rows)


def group_by(table: Table, keys: list[str], agg) -> Table:
    """GROUP BY keys, then apply agg to each group.

    agg is a function receiving (group_rows, key_values) and returning
    a dict of extra output columns.
    """
    buckets: dict[tuple, list[dict]] = {}
    for row in table.rows:
        key = tuple(row[k] for k in keys)
        buckets.setdefault(key, []).append(row)

    rows = []
    for key, group in buckets.items():
        base = {k: v for k, v in zip(keys, key)}
        base.update(agg(group, key))
        rows.append(base)

    return Table(
        name=f"grouped({table.name})",
        columns=keys + sorted({c for r in rows for c in r} - set(keys)),
        rows=rows,
    )


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
