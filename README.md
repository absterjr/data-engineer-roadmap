# Data Engineer Roadmap

An open-source, 8-phase roadmap for becoming a hands-on data engineer / data analyst — built project-by-project, from first principles, and shared publicly as I go.

> Learn by doing. Break things first, then rebuild your own version.

---

## What this is

This repository trails an 8-phase learning plan. Each phase targets one core competency and produces:

1. A **hands-on project** built from scratch (repo + code + write-up)
2. A **LinkedIn post** sharing what was learned

Everything is built with **free tools only** and can be completed in roughly **1–2 hours on weekdays, more on weekends**.

It is designed to be used by others: follow the phases in order, fork the projects, or contribute improvements.

---

## The learning philosophy

To counter "AI rot" — the trap of letting tools do the thinking while your fundamentals decay — this roadmap follows three rules:

- **First principles first.** Before using a tool's high-level API, understand what it is doing under the hood.
- **Fix it, then rebuild it.** Take something broken (a slow query, a buggy pipeline), fix it, then rebuild your own version from scratch.
- **Ship publicly.** Every phase ends with a public project and a LinkedIn post. Public output forces clarity.

---

## The 8 phases

| # | Phase | Focus | Deliverable project |
|---|-------|-------|---------------------|
| 1 | Fundamentals | SQL + Python, from the ground up | Rebuild a mini relational engine (filter / join / group-by) in pure Python |
| 2 | EDA | Exploratory data analysis, statistics, visualization | Full EDA study on a real public dataset with a written report |
| 3 | Databases & data modeling | Schema design, normalization, dimensional modeling | Design + build a warehouse for a fictional e-commerce company |
| 4 | Pipelines | ETL / ELT, orchestration, idempotency, monitoring | End-to-end ELT pipeline: API → land → transform → warehouse |
| 5 | Big data & cloud | Distributed concepts, Spark, object storage, cloud free tiers | Process a large dataset with Spark vs pandas — a measured comparison |
| 6 | ML fundamentals | Features, train/test, evaluation, model serving | Train, package, and serve a model behind a small API |
| 7 | Analytics engineering | dbt, metrics layer, testing, documentation, reverse ETL | A dbt project with staging / marts, tests, and docs |
| 8 | LLM agents on data | Prompting, RAG, embeddings, vector search, tool calling | A "chat with your data" agent: natural language → SQL |

---

## Phase details

### Phase 1 — Fundamentals

**Skills:** SQL joins, window functions, CTEs, query optimization · Python data structures, OOP, error handling, file I/O.

**First-principles project:** Build a tiny relational engine in pure Python that reads CSVs and implements `SELECT`, `WHERE`, `JOIN`, `GROUP BY` and basic aggregation — no SQL libraries. This teaches how SQL actually works under the hood.

**Rebuild task:** Fix a set of poorly-optimized SQL queries, then rewrite them as clean, indexed, explainable queries.

**LinkedIn post:** Why learning SQL by building it beats memorizing syntax — and how it defends against AI rot.

### Phase 2 — EDA

**Skills:** pandas, numpy, matplotlib / seaborn, descriptive statistics, hypothesis testing, data quality checks, communicating findings.

**Project:** A complete EDA on a real public dataset (e.g. retail, taxi, or healthcare): data cleaning, univariate/multivariate analysis, visualizations, and a written report with insights.

**LinkedIn post:** The EDA workflow that catches bad data before it becomes bad decisions.

### Phase 3 — Databases & data modeling

**Skills:** PostgreSQL / SQLite, normalization (1NF–3NF), star & snowflake schemas, dimensional modeling, indexing, transactions.

**Project:** Design a source-normalized schema and a dimensional warehouse (facts + dimensions) for a fictional e-commerce business. Write all DDL, seed it with generated data, and run analytical queries.

**LinkedIn post:** Why the star schema still wins — and how to model a warehouse from an ERD.

### Phase 4 — Pipelines (ETL / ELT)

**Skills:** Extraction from APIs / files, staging, transformation, loading, orchestration (Airflow / Prefect), idempotency, backfills, monitoring, alerting.

**Project:** An end-to-end ELT pipeline: pull data from a public API, land it raw, transform it, and load it into a local warehouse — orchestrated with a scheduler and re-runnable from scratch.

**LinkedIn post:** The anatomy of a production pipeline: idempotency, backfills, and why orchestration matters.

### Phase 5 — Big data & cloud

**Skills:** Distributed computing concepts, Apache Spark (local mode), columnar formats (Parquet), partitioning, object storage, cloud free tiers (GCP / AWS), DuckDB.

**Project:** Take a dataset too large for pandas and process it with Spark locally; measure time, memory, and code complexity vs. pandas; discuss when you truly need big-data tools.

**LinkedIn post:** When pandas breaks: a measured look at Spark, DuckDB, and the cost of distributed compute.

### Phase 6 — ML fundamentals for data engineers

**Skills:** scikit-learn basics, feature engineering, train/test splits, evaluation metrics, model packaging, basic model serving via an API, feature-store concepts.

**Project:** Train a model on a real dataset, evaluate it honestly, package it, and serve it behind a small REST API with a health-checked endpoint.

**LinkedIn post:** What data engineers must know about ML — and where the pipeline hands off to the model.

### Phase 7 — Analytics engineering

**Skills:** dbt (open source), staging / marts layering, tests, documentation, semantic / metrics layer, exposure, reverse ETL.

**Project:** A dbt project on a free data stack (e.g. DuckDB or BigQuery sandbox) with clean staging + mart models, data tests, and auto-generated docs.

**LinkedIn post:** The analytics engineer role: where the data engineer ends and the analyst begins.

### Phase 8 — LLM agents on data

**Skills:** Prompting, RAG, embeddings, vector search (FAISS / Chroma), tool calling, building agents, evaluation of LLM output.

**Project:** A "chat with your data" agent that answers questions over your own dataset — combining retrieval (RAG) with a natural-language-to-SQL tool call, with guardrails and output evaluation.

**LinkedIn post:** Building an LLM agent on your own data — lessons from a real, evaluated build.

---

## How to use this roadmap

1. **Clone or fork** this repo.
2. Work through phases **in order** — each one builds on the last.
3. For each phase, create a project folder in that phase's directory (see [Project layout](#project-layout)).
4. Finish each phase with a **public post** — sharing forces understanding.
5. Pace: **1–2 hrs weekdays, more on weekends**. Expect ~4–6 weeks per phase.

## Project layout

As each phase is completed, its project is added to the repo. The pattern for each phase folder:

```
phase-01-fundamentals/
├── README.md          # write-up: what, why, what I learned
├── notebooks/         # exploration (Jupyter)
├── src/               # your rebuilt implementation
├── data/              # (gitignored unless small/sample)
└── sql/               # for SQL-heavy phases
```

## Progress

| Phase | Status |
|-------|--------|
| 1 — Fundamentals | 🔜 upcoming |
| 2 — EDA | — |
| 3 — Databases & data modeling | — |
| 4 — Pipelines | — |
| 5 — Big data & cloud | — |
| 6 — ML fundamentals | — |
| 7 — Analytics engineering | — |
| 8 — LLM agents on data | — |

> Status is updated as each phase ships. PRs welcome to mark your own progress in your fork.

---

## Contributing

This is an open-source learning resource, and contributions are welcome:

- **Fix a bug** or improve a project in any phase folder.
- **Suggest a better project** or resource for a phase.
- **Add a translation** of the roadmap.
- **Report an issue** if something is broken or confusing.

Please open an issue first for larger changes, and keep contributions in the spirit of the roadmap: free tools, first-principles, beginner-friendly.

---

## License

[MIT](LICENSE) — use it, adapt it, teach with it.
