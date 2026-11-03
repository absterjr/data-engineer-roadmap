"""orchestrator — a miniature Airflow, built from first principles.

Airflow (and Prefect) rest on three ideas, and this file implements all
three in ~150 lines of stdlib Python so each one can be SEEN:

1. A TASK is a function wrapped with metadata: how many retries it
   deserves, how long to wait between them, and what it logs.
2. A DAG (directed acyclic graph) wires tasks together with
   dependencies (task_a >> task_b = "b runs after a"). Running a DAG
   means executing tasks in an order that respects every arrow.
3. A RUN HISTORY records every attempt: status, timestamps, error
   messages. That history is what makes re-runs IDEMPOTENT (a task that
   succeeded before is skipped unless forced) and what turns a pile of
   scripts into a pipeline you can trust at 3am.

Plus one more piece every orchestrator needs: RETRIES with exponential
backoff, because networks are unreliable and "try once, die" is not a
production strategy.
"""
from __future__ import annotations

import sqlite3
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def utc_now() -> str:
    """One canonical timestamp format for the whole pipeline."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# The task
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """One unit of work in the DAG.

    name     : must be unique within the DAG (it keys the run history)
    func     : the work, a callable taking (ctx, **kwargs) — ctx carries
               the run's config (date range, data paths, db connections)
    retries  : how many ADDITIONAL attempts after the first failure
    backoff  : seconds to sleep before retry n (doubles each attempt)
    upstream : tasks that must succeed before this one runs
    """

    name: str
    func: Callable
    retries: int = 1
    backoff: float = 2.0
    upstream: list["Task"] = field(default_factory=list)

    def __rshift__(self, other: "Task") -> "Task":
        """task_a >> task_b  =  "b runs after a" (Airflow's >> operator).

        HOW: appends self to other's upstream list and returns other, so
        chains compose: a >> b >> c works left to right.
        """
        if not isinstance(other, Task):
            raise TypeError(">> only connects Tasks")
        if self in other.upstream:
            return other
        other.upstream.append(self)
        return other

    def ready(self, done: dict[str, str]) -> bool:
        """True when every upstream task has status 'succeeded'."""
        return all(done.get(t.name) == "succeeded" for t in self.upstream)

    def _attempt(self, ctx: dict, attempt: int) -> None:
        """One try. Sleeps with backoff before retries (never the first)."""
        if attempt > 1:
            wait = self.backoff * (2 ** (attempt - 2))
            print(f"      retry {attempt} after {wait:.1f}s backoff ...")
            time.sleep(wait)
        self.func(ctx)

    def run(self, ctx: dict) -> int:
        """Run the task with retries. Returns the number of attempts used.

        Any exception marks the attempt failed; the LAST exception is
        re-raised after retries are exhausted so the DAG can abort.
        """
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 2):  # 1 real + N retries
            try:
                self._attempt(ctx, attempt)
                return attempt
            except Exception as e:  # noqa: BLE001 — an orchestrator must catch everything
                last_error = e
                print(f"      attempt {attempt} failed: {e}")
        print(f"    {self.name} FAILED after {self.retries + 1} attempts")
        raise last_error


# ---------------------------------------------------------------------------
# The DAG
# ---------------------------------------------------------------------------


class DAG:
    """A collection of Tasks wired with dependencies, plus run history.

    run() is the whole point:
      1. topological sort (Kahn's algorithm) — an execution order that
         respects every dependency, and detects cycles
      2. for each task in that order: skip if it already succeeded for
         this run (IDEMPOTENCY — the whole reason re-runs are safe),
         otherwise run it with retries
      3. record every attempt in the meta DB (monitoring)
    """

    def __init__(self, name: str, meta_db: str | Path, force: bool = False):
        self.name = name
        self.tasks: dict[str, Task] = {}
        self.meta_db = Path(meta_db)
        self.force = force

    def task(self, name: str, retries: int = 1, backoff: float = 2.0) -> Callable:
        """Decorator factory: turns a function into a Task by name.

            @dag.task("extract", retries=3)
            def extract(ctx): ...

        Returns the TASK (not the function) so dependencies can be wired
        with `extract >> transform` — the DAG invokes the function through
        the task, never directly.
        """
        def deco(func: Callable) -> "Task":
            t = Task(name=name, func=func, retries=retries, backoff=backoff)
            self.tasks[name] = t
            return t
        return deco

    def _topo_sort(self) -> list[Task]:
        """Kahn's algorithm: repeatedly emit tasks with no pending deps.

        HOW: count how many upstream tasks each task still has; process
        the ready ones first. If anything is left at the end, the graph
        has a CYCLE — an orchestrator must refuse that, not loop forever.
        """
        indegree = {t.name: len(t.upstream) for t in self.tasks.values()}
        dependents: dict[str, list[Task]] = {}
        for t in self.tasks.values():
            for u in t.upstream:
                dependents.setdefault(u.name, []).append(t)

        ready = [t for t in self.tasks.values() if indegree[t.name] == 0]
        order: list[Task] = []
        while ready:
            t = ready.pop(0)
            order.append(t)
            for dep in dependents.get(t.name, []):
                indegree[dep.name] -= 1
                if indegree[dep.name] == 0:
                    ready.append(dep)

        if len(order) != len(self.tasks):
            stuck = [n for n, d in indegree.items() if d > 0]
            raise ValueError(f"cycle detected in DAG, stuck tasks: {stuck}")
        return order

    # -- run history (the meta DB) ------------------------------------------

    def _init_meta(self) -> sqlite3.Connection:
        """Create the pipeline_runs table if needed, return a connection."""
        self.meta_db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.meta_db)
        con.execute(
            """CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id    TEXT NOT NULL,
                task      TEXT NOT NULL,
                status    TEXT NOT NULL,
                attempts  INTEGER NOT NULL,
                started   TEXT NOT NULL,
                finished  TEXT,
                error     TEXT,
                detail    TEXT,
                PRIMARY KEY (run_id, task)
            )"""
        )
        return con

    def _record(self, con, run_id, task, status, attempts, started, finished, error, detail):
        con.execute(
            "INSERT OR REPLACE INTO pipeline_runs "
            "(run_id, task, status, attempts, started, finished, error, detail) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (run_id, task, status, attempts, started, finished, error, detail),
        )
        con.commit()

    def previous_succeeded(self, con, run_id, task_name) -> bool:
        """Idempotency check: did this task already succeed for this run?"""
        row = con.execute(
            "SELECT status FROM pipeline_runs WHERE run_id = ? AND task = ?",
            (run_id, task_name),
        ).fetchone()
        return row is not None and row[0] == "succeeded"

    def run(self, ctx: dict, run_id: str) -> bool:
        """Execute the DAG. Returns True only if EVERY task succeeded."""
        con = self._init_meta()
        order = self._topo_sort()
        done: dict[str, str] = {}

        print(f"\n=== DAG {self.name} — run {run_id} "
              f"({'FORCED' if self.force else 'incremental'}) ===")
        for t in order:
            if not t.ready(done):
                print(f"  [skip]   {t.name} (upstream failed)")
                continue

            if not self.force and self.previous_succeeded(con, run_id, t.name):
                print(f"  [cached] {t.name} (already succeeded for this run)")
                done[t.name] = "succeeded"
                continue

            started = utc_now()
            print(f"  [run]    {t.name} ...")
            try:
                attempts = t.run(ctx)          # returns the attempts actually used
                status, error, detail = "succeeded", None, None
            except Exception as e:
                attempts = t.retries + 1
                status, error, detail = "failed", str(e), traceback.format_exc()[-2000:]
            finished = utc_now()
            self._record(con, run_id, t.name, status, attempts,
                         started, finished, error, detail)
            done[t.name] = status
            if status == "failed":
                print(f"  [FAIL]   {t.name}")
                break  # downstream tasks will be [skip]ped by ready()

        all_ok = all(s == "succeeded" for s in done.values())
        con.close()
        print(f"=== DAG {self.name}: {'SUCCESS' if all_ok else 'FAILURE'} ===")
        return all_ok

    def status(self, limit: int = 10) -> None:
        """Print the most recent runs from the meta DB."""
        con = self._init_meta()
        rows = con.execute(
            "SELECT run_id, task, status, attempts, started, finished, error "
            "FROM pipeline_runs ORDER BY started DESC, task LIMIT ?",
            (limit,),
        ).fetchall()
        if not rows:
            print("no runs recorded yet")
        for r in rows:
            err = f"  err={r[6][:60]}" if r[6] else ""
            print(f"  {r[0]}  {r[1]:<12} {r[2]:<10} attempts={r[3]} "
                  f"{r[4]} -> {r[5]}{err}")
        con.close()

    def reset(self) -> None:
        """Wipe the run history (and the data dirs) for a clean demo."""
        for p in [self.meta_db]:
            if p.exists():
                p.unlink()
        print(f"reset: deleted {self.meta_db}")