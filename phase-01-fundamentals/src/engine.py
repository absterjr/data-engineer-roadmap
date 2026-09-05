"""A tiny relational engine built from first principles.

Reads a CSV and supports SELECT, WHERE, JOIN, GROUP BY, ORDER BY, LIMIT,
window functions and basic aggregation — implemented by hand, with NO
SQL libraries.

Read this file top to bottom and you effectively learn how a database
works: everything SQL does is one of these ~15 small functions.

-----------------------------------------------------------------------
HOW TO READ THIS FILE
-----------------------------------------------------------------------
1. `Table`       — the data structure everything operates on
2. `read_csv`    — how a text file becomes a table (with type coercion)
3. the relational ops — project (SELECT), where (WHERE), extend, join,
   group_by, order_by, limit. Each one takes a Table IN and returns a
   NEW Table OUT. None of them modify the input. That "immutable in,
   new out" rule is what makes the engine predictable.
4. aggregates    — the summarizing functions used inside group_by
5. window funcs  — like GROUP BY, but every row survives

Day 2 additions: type coercion on load, `extend`, `order_by`, `limit`,
aggregates.
Day 6 additions: window functions, LEFT JOIN (hash join), clear errors.
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
    """An in-memory table: a list of column names and a list of rows.

    HOW IT WORKS:
      - `columns` is a list of strings, e.g. ["Country", "Revenue"]
      - `rows`    is a list of DICTS, one per row, where each dict maps
                  column-name -> value, e.g. {"Country": "UK", "Revenue": 120.5}
      - Dict-per-row (instead of list-per-row) is what makes column
        access by NAME possible: row["Country"]. Real databases store
        rows differently, but for learning, dicts are the clearest.

    The @dataclass decorator auto-generates __init__ and __repr__ so we
    don't have to write that boilerplate by hand.
    """

    name: str
    columns: list[str]
    rows: list[dict] = field(default_factory=list)

    @property
    def width(self) -> int:
        """Number of columns (a 'property' reads like an attribute but is a method)."""
        return len(self.columns)

    def __len__(self) -> int:
        """Makes len(table) return the row count, like len(list)."""
        return len(self.rows)

    def __repr__(self) -> str:
        """What you see when you print(table) — a one-line summary."""
        return f"Table({self.name!r}, cols={self.columns}, rows={len(self.rows)})"


def _require_columns(table: Table, columns, op: str) -> None:
    """Fail EARLY and LOUDLY when a column doesn't exist.

    WHAT: checks every name in `columns` against the table's columns.
    WHY:  without this, a typo like "Cuntry" explodes much later with a
          confusing KeyError deep inside a loop. Databases do the same
          check when they parse a query — "column not found" is the
          error you get from Postgres for exactly this mistake.
    The leading underscore in the name is Python convention for
    "internal helper, not part of the public API".
    """
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
    """Turn one CSV string into a real Python value (int / float / None / str).

    WHAT: CSV files have no types — everything is text. "6", "2.55" and
          "" all arrive as strings. This function decides what each
          string REALLY is, one cell at a time.

    HOW (a cascade of attempts — first match wins):
      1. strip whitespace, then treat '', 'nan', 'NA', 'NULL' as None
         (Python's None == SQL's NULL = "no value")
      2. try int("6")          -> 6      (whole numbers)
      3. try float("2.55")     -> 2.55   (decimals)
         - special case: "17850.0" becomes int 17850, not 17850.0,
           because a CustomerID of 17850.0 is ugly and groups wrong
      4. anything else stays a string ("United Kingdom", "C536379")

    THE LESSON: this is exactly what pandas does when it 'infers' dtypes,
    and what a database does when you declare a column type. Types are a
    DECISION someone makes — here, that someone is this function.
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
        # is_integer() is True for 17850.0 but False for 2.55
        return int(f) if f.is_integer() else f
    except ValueError:
        return v


def read_csv(path: str | Path, name: str | None = None, coerce: bool = True) -> Table:
    """Read a CSV file into a Table. First row of the file = column names.

    HOW:
      - csv.DictReader is from Python's standard library. It reads the
        header row once, then yields every following row as a dict
        {header: value}. That's why our Table stores rows as dicts.
      - if coerce=True (the default), every cell goes through _coerce()
        so numbers arrive as numbers, not strings.
      - the table's name defaults to the filename without extension,
        so 'online_retail.csv' becomes Table('online_retail').
    """
    path = Path(path)
    if not path.exists():
        # Fail with instructions, not a bare traceback — future-you will
        # thank present-you.
        raise FileNotFoundError(
            f"read_csv: {path} does not exist. If this is the Online Retail "
            "dataset, get it with: python scripts/fetch_online_retail.py"
        )
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        if coerce:
            # _coerce every cell of every row (541,909 rows x 8 cols here)
            rows = [{k: _coerce(v) for k, v in row.items()} for row in reader]
        else:
            rows = [dict(row) for row in reader]
    return Table(name=name or path.stem, columns=columns, rows=rows)


# ---------------------------------------------------------------------------
# Relational operations
#
# Every operation below follows the same contract:
#     Table in -> NEW Table out (the input is never modified)
# which is why queries.py can chain them like Lego.
# ---------------------------------------------------------------------------


def project(table: Table, columns: list[str]) -> Table:
    """SELECT: keep only the given columns (in that order).

    WHAT:  project(sales, ["Country", "Revenue"]) is SQL's
           "SELECT Country, Revenue FROM sales".

    HOW:   for each row, build a NEW dict containing only the requested
          keys, in the requested order. A dict comprehension inside a
          list comprehension = one pass over the data, O(rows * cols).
    """
    _require_columns(table, columns, "project")
    return Table(
        name=table.name,
        columns=columns,
        rows=[{c: row[c] for c in columns} for row in table.rows],
    )


def where(table: Table, predicate: Callable[[dict], bool]) -> Table:
    """WHERE: keep only the rows for which predicate(row) is True.

    WHAT:  where(sales, lambda r: r["Country"] == "UK") is SQL's
           "WHERE Country = 'UK'".

    HOW:   `predicate` is a FUNCTION we pass in (a 'higher-order'
          operation). The lambda takes one row-dict and answers True or
          False; a list comprehension keeps the survivors.

    WHY a function instead of a string like "Country == 'UK'"?
    Parsing strings is what makes real databases huge. Passing Python
    functions gives us full power with zero parser.
    """
    return Table(
        name=table.name,
        columns=table.columns,
        rows=[row for row in table.rows if predicate(row)],
    )


def extend(table: Table, expr: Callable[[dict], object], name: str) -> Table:
    """SELECT expr AS name — add a computed column.

    WHAT:  extend(sales, lambda r: r["Quantity"] * r["UnitPrice"], "Revenue")
           is SQL's "SELECT Quantity * UnitPrice AS Revenue".

    HOW:   copy each row (dict(row) — the copy matters! we must not
          mutate the input table), evaluate expr on the copy, store the
          result under the new column name.
    """
    rows = []
    for row in table.rows:
        new_row = dict(row)          # shallow copy: safe to add a key
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
    """JOIN: glue two tables together row-by-row where the keys match.

    WHAT:  join(sales, regions, "Country", "Country") is SQL's
           "FROM sales JOIN regions ON sales.Country = regions.Country".
           how="left" makes it a LEFT JOIN: every left row survives even
           with no match (right-side columns become None).

    HOW — the hash join (the same trick real databases use):
      1. build an INDEX of the right table once: a dict mapping each
         key value -> list of rows with that key. O(m) work.
      2. for each left row, LOOK UP its key in that dict — O(1) average.
      Total: O(n + m), versus the nested-loop version's O(n * m).
      (Phase 1's first join was a nested loop: 541k x 38 = 20M checks.
       The hash join does ~542k. Same result, wildly faster.)

    DETAILS:
      - right-side columns that already exist on the left are dropped
        (the join key is shared, so the values are equal by construction)
      - LEFT JOIN with no match -> right columns filled with None,
        which is SQL's NULL-filled row.
    """
    if how not in ("inner", "left"):
        raise ValueError(f"join: how must be 'inner' or 'left', got {how!r}")
    _require_columns(left, [on_left], "join")
    _require_columns(right, [on_right], "join")

    new_cols = [c for c in right.columns if c not in left.columns]
    columns = left.columns + new_cols

    # step 1: the hash index — key -> list of right rows with that key
    index: dict[object, list[dict]] = {}
    for rrow in right.rows:
        index.setdefault(rrow[on_right], []).append(rrow)

    # step 2: probe the index once per left row
    rows = []
    for lrow in left.rows:
        matches = index.get(lrow[on_left], [])
        if matches:
            for rrow in matches:
                merged = {k: v for k, v in rrow.items() if k in new_cols}
                rows.append({**lrow, **merged})
        elif how == "left":
            # no match, but LEFT JOIN keeps the row with NULL right side
            rows.append({**lrow, **{c: None for c in new_cols}})
    return Table(name=f"({left.name} {how}⋈ {right.name})", columns=columns, rows=rows)


def group_by(table: Table, keys: list[str], aggs) -> Table:
    """GROUP BY: bucket rows by key, then summarize each bucket.

    WHAT:  group_by(sales, ["Country"], {"Revenue": sum_("Revenue")})
           is SQL's "SELECT Country, SUM(Revenue) FROM sales GROUP BY Country".

    HOW — two passes:
      1. BUCKET: walk every row once, compute its key tuple
         (e.g. ("United Kingdom",)), and append the row to that key's
         list in a dict. After this pass, `buckets` is:
             {("UK",): [row1, row7, ...], ("France",): [row2, ...], ...}
      2. AGGREGATE: for each bucket, start a result row with the key
         values, then call each aggregate function on the group.

    `aggs` accepts two shapes:
      - a dict:    {"Revenue": sum_("Revenue")}   (name -> function)
      - a callable: fn(group_rows, key) -> dict    (full control)
    """
    _require_columns(table, keys, "group_by")

    # pass 1: bucket (setdefault = "get the list, or create it if absent")
    buckets: dict[tuple, list[dict]] = {}
    for row in table.rows:
        key = tuple(row[k] for k in keys)
        buckets.setdefault(key, []).append(row)

    # pass 2: summarize each bucket
    rows = []
    for key, group in buckets.items():
        base = dict(zip(keys, key))          # {"Country": "UK"}
        if callable(aggs):
            base.update(aggs(group, key))
        else:
            for name, fn in aggs.items():
                base[name] = fn(group, key)
        rows.append(base)

    # output columns: keys first, then whatever the aggregates produced
    columns = keys
    if rows:
        columns = columns + [c for c in rows[0] if c not in keys]

    return Table(name=f"grouped({table.name})", columns=columns, rows=rows)


def order_by(table: Table, key: str, desc: bool = False) -> Table:
    """ORDER BY: sort rows by a column. Stable sort: ties keep input order.

    WHY IT EXISTS AS A SEPARATE STEP: GROUP BY buckets come out in
    whatever order the scan happened to visit them. SQL makes no order
    guarantee either — "it looks sorted" is not a guarantee, ORDER BY is.

    HOW: Python's sorted() is stable (equal keys keep their relative
    order). The sort key is a TUPLE (is_none, value) so that None sorts
    last in BOTH directions — comparing None to a float directly would
    crash, and SQL has its own (different!) NULL-ordering rules.
    """
    _require_columns(table, [key], "order_by")
    rows = sorted(table.rows, key=lambda r: (r[key] is None, r[key]), reverse=desc)
    return Table(name=table.name, columns=table.columns, rows=rows)


def limit(table: Table, n: int) -> Table:
    """LIMIT n: keep only the first n rows. Usually used after order_by
    for 'top N' questions."""
    return Table(name=table.name, columns=table.columns, rows=table.rows[:n])


# ---------------------------------------------------------------------------
# Aggregates (for use with group_by)
#
# These are FUNCTION FACTORIES: sum_("Revenue") doesn't sum anything yet —
# it RETURNS a function that will. That's why group_by can call
# fn(group_rows, key) without knowing which column you wanted.
# ---------------------------------------------------------------------------


def count(rows: list[dict], key=None) -> int:
    """COUNT(*) — just the number of rows in the group."""
    return len(rows)


def sum_(col: str) -> Callable[[list[dict], tuple], float]:
    """SUM(col) — add up one column across the group, skipping NULLs.

    HOW: returns a CLOSURE — a function that 'remembers' col. SQL's
    SUM(Revenue) maps to sum_("Revenue") here; the trailing underscore
    avoids clashing with Python's built-in sum().
    """

    def agg(rows: list[dict], key=None) -> float:
        return sum(r[col] for r in rows if r[col] is not None)

    return agg


def mean(col: str) -> Callable[[list[dict], tuple], float | None]:
    """AVG(col) — sum / count, ignoring NULLs. None if no values at all
    (SQL returns NULL for AVG of an empty set, not 0 — same rule)."""

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
# GROUP BY collapses rows: 541,909 rows in, 38 rows out.
# WINDOW FUNCTIONS do NOT collapse: every row survives, and a new column
# carries the window's answer for that row. "Top 3 per group", "running
# total", "% of total" — all impossible with GROUP BY alone.
#
# KEY MECHANIC: windows never reorder rows. So we bucket (index, row)
# PAIRS, compute values in whatever order the window needs, then write
# each result back at the row's ORIGINAL index. Input order in = order out.
# ---------------------------------------------------------------------------


def _partition(table: Table, partition_keys: list[str]) -> dict[tuple, list[tuple[int, dict]]]:
    """Split rows into buckets of (original_index, row) pairs.

    The index travels with the row so results can be written back to
    the exact same position later. An empty partition_keys = one single
    bucket containing everything (SQL's OVER () with no PARTITION BY).
    """
    _require_columns(table, partition_keys, "window function")
    buckets: dict[tuple, list[tuple[int, dict]]] = {}
    for i, row in enumerate(table.rows):
        key = tuple(row[k] for k in partition_keys) if partition_keys else ()
        buckets.setdefault(key, []).append((i, row))
    return buckets


def _order_partition(group, order_key: str | None, desc: bool) -> list[tuple[int, dict]]:
    """Sort one partition's (index, row) pairs by order_key. NULLs last.

    If no order_key is given, the partition keeps its input order —
    which is what SQL does too (no ORDER BY in OVER = arbitrary order).
    """
    if order_key is None:
        return group
    return sorted(group, key=lambda ir: (ir[1][order_key] is None, ir[1][order_key]), reverse=desc)


def _window(table: Table, partition_keys, order_key, desc, name: str) -> list[dict]:
    """Shared plumbing for all window functions.

    Allocates the output rows: copies of the input rows (input order
    preserved!) with the new column set to None as a placeholder.
    Each window function then fills its own placeholder in.
    """
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
    """ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...) — 1, 2, 3...

    WHAT: ranks rows within each partition, every row a distinct number.
    The classic use: "top N per group" — number them, then WHERE rn <= N.

    HOW: enumerate each ordered partition starting at 1, write the
    number back at the row's original index.
    """
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
    """RANK() OVER (...): ties share a rank, then the next rank SKIPS.

    Example revenues [100, 90, 90, 80] -> ranks [1, 2, 2, 4].
    Row 4 gets rank 4 (not 3) because two rows tied ahead of it —
    that's the 'gap' and it's what makes RANK different from DENSE_RANK.

    HOW: walk the ordered partition; when the value CHANGES from the
    previous row, the rank jumps to the current 1-based position.
    """
    partition_keys = partition_keys or []
    _require_columns(table, [c for c in partition_keys + [order_key] if c], "rank")
    result = _window(table, partition_keys, order_key, desc, name)
    _sentinel = object()  # unique marker: "no previous value yet"
    for group in _partition(table, partition_keys).values():
        prev, current = _sentinel, 0
        for pos, (i, row) in enumerate(_order_partition(group, order_key, desc), start=1):
            val = row[order_key]
            if prev is _sentinel or val != prev:
                current = pos      # tie -> keep current; new value -> jump
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
    """DENSE_RANK() OVER (...): ties share a rank, NO gaps.

    Same data as in rank(): [100, 90, 90, 80] -> [1, 2, 2, 3].
    The counter only advances when the value actually changes.
    """
    partition_keys = partition_keys or []
    _require_columns(table, [c for c in partition_keys + [order_key] if c], "dense_rank")
    result = _window(table, partition_keys, order_key, desc, name)
    _sentinel = object()
    for group in _partition(table, partition_keys).values():
        prev, current = _sentinel, 0
        for i, row in _order_partition(group, order_key, desc):
            val = row[order_key]
            if prev is _sentinel or val != prev:
                current += 1       # advance only on a value change
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
    """SUM(col) OVER (PARTITION BY ... ORDER BY ...) — a running total.

    WHAT: for each row, the sum of col for ALL rows up to and including
    it, in window order. The classic "cumulative revenue by month".

    HOW: walk the ordered partition once, carrying an accumulator.
    One addition per row = O(n) per partition. NULLs count as 0.
    """
    partition_keys = partition_keys or []
    _require_columns(table, [col] + [c for c in partition_keys + [order_key] if c], "running_sum")
    result = _window(table, partition_keys, order_key, desc, name)
    for group in _partition(table, partition_keys).values():
        acc = 0.0
        for i, row in _order_partition(group, order_key, desc):
            acc += row[col] or 0   # NULL -> 0 (SQL's default frame does too)
            result[i][name] = acc
    return Table(name=table.name, columns=table.columns + [name], rows=result)


def partition_sum(
    table: Table,
    col: str,
    partition_keys: list[str] | None = None,
    name: str = "partition_total",
) -> Table:
    """SUM(col) OVER (PARTITION BY ...) — the partition's total, repeated
    on EVERY row of that partition. No ORDER BY = the window is the whole
    partition. This is how you compute "% of total" in SQL:

        Revenue / SUM(Revenue) OVER () * 100

    HOW: two passes — total each partition (one accumulator per key),
    then stamp the total onto every row of that partition.
    """
    partition_keys = partition_keys or []
    _require_columns(table, [col] + partition_keys, "partition_sum")

    # pass 1: one total per partition key
    totals: dict[tuple, float] = {}
    for row in table.rows:
        key = tuple(row[k] for k in partition_keys) if partition_keys else ()
        totals[key] = totals.get(key, 0.0) + (row[col] or 0)

    # pass 2: stamp the total onto every row
    result = _window(table, partition_keys, None, False, name)
    for row in result:
        key = tuple(row[k] for k in partition_keys) if partition_keys else ()
        row[name] = totals[key]
    return Table(name=table.name, columns=table.columns + [name], rows=result)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Command-line entry point: python engine.py path/to/data.csv"""
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