# Sheets and sources

Editing the Google Sheet sources behind DIBELS, and the two rules that have
broken this more than once.

## Named ranges: the recurring trap

`sheet_range` in `sources-external.yml` points at a Google Sheets **named
range**, not a tab title -- and a spreadsheet can carry several similarly-named
ranges left over from prior schema versions. This cost real back-and-forth twice
in one build:

- The foundation goals spreadsheet has BOTH
  `src_google_sheets__dibels_foundation_goals` (single underscore -> tab
  "Foundation Goals V1", 8 cols, legacy) AND
  `src_google_sheets__dibels__foundation_goals` (double underscore -> tab
  "Foundation Goals", 12 cols, current). Pointing `sheet_range` at the wrong one
  fails with a BigQuery type-conversion error that looks like a data problem
  ("Could not convert value to integer") but is actually a wrong-range problem
  -- the columns don't line up because it's reading a different tab entirely.
- A named range can also be **row-bounded**.
  `src_google_sheets__dibels__foundation_goals` was capped at 191 rows total; a
  203-row paste silently truncated the tail (whichever region got pasted last)
  with no error at all -- the build just quietly returned fewer rows. Always ask
  for headroom past the current row count when a new named range is created, and
  if a rebuilt row count is suspiciously short, check `count(*)` per region/year
  before assuming a parsing bug.

**Verify the real named range before writing `sheet_range`, every time**:

```python
ss = svc.spreadsheets().get(spreadsheetId="<id>").execute()
titles = {s["properties"]["sheetId"]: s["properties"]["title"] for s in ss["sheets"]}
for nr in ss.get("namedRanges", []):
    print(nr["name"], "->", titles.get(nr["range"].get("sheetId")), nr["range"])
```

### Never edit `sources-external.yml` with a forward-scanning regex

The file holds ~100 source blocks at identical indentation, and **not every one
has a `columns:` block** -- several rely on BigQuery autodetect. So a pattern
like "find this source name, then find the next `columns:`" walks straight past
its own block into a later source and replaces the wrong list, with no error.
That is exactly how `src_google_sheets__gpa_goals` lost its `org_level`,
`schoolid`, `metric`, `threshold`, `direction` and `goal` columns during the
bm_goals cutover -- they were overwritten with bm_goals' 43. Caught only by
reading the diff afterwards.

Edit one source by **bounding the block first**: find its
`      - name: <source>` line, find the next line starting `      - name: src_`,
and operate only between them. That is what the throwaway source-wiring script
used for the bm_goals cutover did -- it moved `sheet_range`, replaced or
inserted the `columns:` list, and asserted it had found exactly one
`sheet_range` and at most one `columns:` inside the block.

Then **audit every removed line** before trusting it:

```bash
git diff <the yml> | grep '^-' | grep -v '^---' | sort | uniq -c
```

For a `sheet_range` move plus a column widen, the only removals should be the
old `sheet_range` line(s). Anything else is collateral.

Two follow-on gotchas from the same cutover:

- An all-blank column autodetects as **STRING**, and a trailing all-blank column
  is **dropped entirely**. Migrating a widened sheet whose new columns are empty
  (IEP/MLL placeholders) therefore fails a `select *` contract on type
  mismatches and missing columns until the source declares `columns:`
  explicitly. Declaring them is the fix, not casting downstream.
- Re-stage after any range move:
  `stage_external_sources --target dev --vars '{ext_full_refresh: true}'` for
  local work, and the same with `--target staging` before pushing, or dbt Cloud
  CI fails "table not found" on the `zz_stg_` external. The staging run needs
  the user -- it drops and recreates a shared table.
- **Stage last.** Any edit to a source's `columns:` invalidates an external that
  is already staged, and `stage_external_sources` SKIPS an existing table unless
  `ext_full_refresh: true`. So the order is: settle the declaration, stage dev,
  stage staging, push. Staging mid-way costs a CI round -- it did here, twice:
  first a contract mismatch where the source declared `float64` from the rpt_
  model's `ceiling()` output while the consumer's contract said `int64` (counts
  are integral, so `int64` was right), then the mirror image once the yml was
  fixed but the staged external still carried the old type.

## Always hand over the WHOLE sheet, never a patch

The Expected Assessments tabs run to thousands of rows -- V1 is 3,681, the
by-levels range 3,588. **Never ask the user to find and replace a subset**: no
"delete the 442 Benchmark rows where region is Miami and paste these", no
"insert these 216 rows after the AY2025 block". Filtering a long sheet by hand
to delete some rows and paste others is slow, unverifiable, and one mis-set
filter away from destroying rows nobody notices are gone. It has already cost
one near-miss this project, when a delete removed 12 `type = 'LIT'` Benchmark
rows for the current year and only a BigQuery time-travel read got them back.

So every script that modifies an existing tab **emits the full tab, corrected
rows in place**, and the handover is "select all, paste over". That makes the
operation idempotent, reviewable as a row count, and impossible to half-apply.
The V1 `Month/Round` fix is the model: its throwaway script walked all 3,681
rows in original order, rewrote only the `Month/Round` cell on Benchmark rows
whose value disagreed with `reporting__terms`, passed every PM row and every
already-correct row through untouched, and printed a per-key summary of what it
changed so the diff was auditable before pasting.

**The line is whether existing rows change, not how many rows there are.**

| Kind of change                                | Handover                                                                          |
| --------------------------------------------- | --------------------------------------------------------------------------------- |
| Modifies or removes existing rows             | Whole tab, corrected in place. "Select all, paste over."                          |
| Only adds rows for a new year, season or band | The new rows alone. Appending needs no filtering, so it carries none of the risk. |

Where each script sits today, so a successor does not have to read them all:

- Whole-tab, already compliant -- the one-shot sheet fixes (the V1 `Month/Round`
  rewrite, the derived-column backfill, the `measure_standard_level` cohort
  split). All were run once and deleted; the sections below record what each
  did.
- Append-only, correctly partial -- `generate_pm_expected_assessments_rows.py`,
  `generate_nj_lit_plit_rows.py`, `generate_miami_lit_plit_rows.py`,
  `roll_forward_expected_assessments_season.py`.

If a new script needs to change rows that already exist, it belongs in the first
group. Do not add one to the second group that also edits in place.

The three `generate_*` scripts are year-agnostic: each takes `--academic-year`
(labelled by the fall, so SY26-27 is `2026`) and a `--rounds` TSV transcribed
from that year's T&L PM rounds doc. The TSV is not committed; transcribe it each
year. Each script's module docstring documents its own `--rounds` columns with
example rows.

Corollaries:

- Print what changed, grouped and counted --
  `2024 Miami MOY January -> December (46 rows)`. A row count alone does not
  prove the right cells moved.
- Verify after the paste by rebuilding the `stg_` model and re-querying, not by
  eyeballing the sheet. Google Sheets externals read live, but the `stg_` table
  is frozen at its last build.
- If a script cannot express the change as a whole-tab rewrite, that is a signal
  the change is not well enough understood yet -- work it out before handing a
  person a filter to apply.
- The same applies to `reporting__terms`: hand over the complete replacement
  rather than a delete-these-then-add-those instruction.
