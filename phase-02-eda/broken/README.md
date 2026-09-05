# Fix-it-first: broken EDA

`broken_eda.py` runs end-to-end. It prints confident, specific numbers.
**Every business conclusion it draws is wrong.** There are 8 bugs hiding
in ~90 lines.

## Rules

1. Run it: `python broken/broken_eda.py` (from `phase-02-eda/`)
2. For each output line, ask: *do I believe this number?* Compare against
   what Phase 1 already established (541,909 rows, ~25% missing
   CustomerID, UK ≈ 84% of revenue, November peak, thousands of returns).
3. Find all 8 bugs. For each one, classify it: **CRASH** or **SILENT**.
   The silent ones are the career-ending kind.
4. Fix them without opening `src/` — that's the rebuilt reference.
5. Done when: revenue ≈ **£10.7M**, UK share ≈ **84.6%**, busiest month
   **11**, unique customers **≈ 4,372**, returned line items **1,336**.

## Compare side by side

`broken_eda_fixed.py` is the corrected twin: same functions, same
signatures, same report — every fix carries a `BUG n FIX` comment
explaining what was wrong and why.

```bash
# terminal diff
git diff --no-index broken/broken_eda.py broken/broken_eda_fixed.py

# or in VS Code: select both files in the Explorer,
# right-click -> "Compare Selected"
```

Read it function by function: for each pair, first predict what the fix
was, then check the comment.

## Hints (one per bug, mild spoilers)

1. "After cleaning" loses a quarter of the rows. What did `dropna()` throw away?
2. The returns analysis says there are no returns. Where did they go?
3. £16.1M is more than the store ever made. `sum × mean` ≠ `sum of products`.
4. Saudi Arabia is the smallest spender in the dataset. Check the sort direction.
5. Read the pandas warning. Did the `Share` column survive?
6. The data ends in December 2011. What does the busiest-month query assume?
7. `len(df)` is not a customer count.
8. One more: `clean()` deletes the returns *before* `count_returns()` looks for them. Order matters.

<details>
<summary><b>Answers — full spoilers, open only after trying</b></summary>

| # | Bug | Type | Fix |
|---|-----|------|-----|
| 1 | `df.dropna()` drops any row with **any** NaN — 143,985 rows gone (missing `CustomerID` or `Description`) | silent | Drop only what the analysis needs, or flag: `df["HasCustomer"] = df["CustomerID"].notna()` |
| 2 | `clean()` removes `Quantity <= 0`, so returns vanish before any return analysis | silent | Keep returns; exclude them from *revenue* frames only |
| 3 | `sum(Quantity) * mean(UnitPrice)` — mean price × total items is meaningless | silent | `df["Revenue"].sum()` after computing `Quantity * UnitPrice` per row |
| 4 | `sort_values()` ascending + `head()` = the *smallest* countries labeled "top" | silent | `sort_values(ascending=False)` or `.nlargest(n)` |
| 5 | `uk["Share"] = ...` on a slice — chained assignment; `SettingWithCopyWarning`, column never created | silent | `df.loc[mask, "Share"] = ...` or assign on a `.copy()` |
| 6 | Filters `year == 2012` — the data ends Dec 2011; empty frame → `idxmax()` raises | crash | Check the date range first; analyze the year you actually have |
| 7 | `len(df)` counted as "unique customers" | silent | `df["CustomerID"].nunique()` |
| 8 | `count_returns` re-filters `Quantity > 0` then counts negatives — always 0 | silent | Count returns on the unfiltered frame (`IsReturn` flag) |

Meta-lesson: **7 of 8 bugs are silent.** Only one crashes. Broken data
analysis doesn't announce itself — it prints a number and moves on.
</details>