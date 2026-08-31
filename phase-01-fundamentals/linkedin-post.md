# Phase 1 — LinkedIn post (draft)

Post for publishing after Phase 1 ships. Plan: [Why learning SQL by building it beats memorizing syntax — and how it defends against AI rot].

---

**Title / first line:**

Last week I rebuilt SQL from scratch. Not to get faster at writing it — to get faster at *understanding* it.

**Body:**

Every day I work with tools that write SQL for me. LLMs, copilots, chatbots — they draft window-function queries in seconds. And that's exactly why I'm building things by hand again.

I call it "AI rot": the slow decay of fundamentals when the tool does the thinking. If I can't explain why a query is slow, or spot the wrong number hiding in a GROUP BY, the tool isn't helping me. It's hiding from me.

So I'm spending my evenings rebuilding the foundations, in public, as an open-source 8-phase roadmap. Phase 1: a mini relational engine in pure Python — no SQL libraries. Just the building blocks a real database uses: WHERE, GROUP BY, JOIN, ORDER BY, LIMIT, aggregates — implemented by hand.

Five things building it taught me that tutorials never did:

1. **SQL doesn't run top-to-bottom.** FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT. Put an aggregate in WHERE and the database tells you off — aggregates don't exist until the groups do.

2. **GROUP BY order is accidental.** Buckets come out in whatever order the engine happened to scan. That's why ORDER BY exists — and why "it looks sorted" is not a guarantee.

3. **Indexes are easy to defeat.** `LIKE '%2011%'` and `substr(date, 1, 7)` force a full scan of 541,909 rows — even with an index. A range predicate (`>= '2011-01-01' AND < '2012-01-01'`) uses it. I proved it with EXPLAIN QUERY PLAN, before and after.

4. **The data is always messier than the demo.** 25% of the Online Retail dataset has no customer ID. One stock code carries four different descriptions, including "wrongly marked carton 22804". A query can be perfect and the answer still wrong.

5. **WHERE filters rows. HAVING filters groups.** That one sentence would have saved me hours as a beginner.

The whole thing is on GitHub (link in comments): an 8-phase roadmap, built project-by-project. Every commit is logged in a journal with links, and there's a beginner guide with a SQL-to-engine cheat sheet. It's yours to use, fork, or contribute to.

If you're a data engineer or analyst: what's the one fundamental you'd rebuild if you had to?

#DataEngineering #SQL #FirstPrinciples #LearningInPublic

---

**Publish checklist:**
- [ ] Add repo link (paste in comments or first comment)
- [ ] Review against [repo](https://github.com/absterjr/data-engineer-roadmap) — verify numbers (541,909 rows, 25% missing CustomerID, four descriptions for 85123A)
- [ ] Optional: add 2-3 emojis sparingly for readability
- [ ] Publish, then add a short follow-up comment with the repo URL