---
name: carat-dashboard
description: >-
  Use when any question or task touches the CARAT dashboard (College Admission
  Readiness Assessments Tracker) or its lineage. Triggers: adding Illuminate
  practice SAT/ACT assessments for a new administration, generating or auditing
  raw-to-scale-score rows for the act_scale_score_key sheet, a practice score
  not appearing on the dashboard, goal thresholds not matching, academic-year
  rollover, or working on int_assessments__college_assessment_practice,
  int_tableau__college_assessment_roster_scores,
  rpt_tableau__college_assessment_dashboard_current, or _benchmark_calcs and
  their upstream models.
---

# CARAT Dashboard Data Model

## Always read first

- Design spec:
  [`docs/superpowers/specs/2026-07-31-carat-illuminate-interims-design.md`](../../../docs/superpowers/specs/2026-07-31-carat-illuminate-interims-design.md)
- Exposure: `college_admission_readiness_assessments_tracker_carat`

The spec is authoritative for the designation/conversion split, the two-section
SAT total, and which pre-existing defects were deliberately left unfixed.

## Orientation

Two separate score pipelines feed CARAT, and confusing them is the most common
source of wrong answers:

| Pipeline | Hub model                                      | `test_type` | Source                                   |
| -------- | ---------------------------------------------- | ----------- | ---------------------------------------- |
| Official | `int_assessments__college_assessment`          | `Official`  | kippadb + collegeboard                   |
| Practice | `int_assessments__college_assessment_practice` | `Practice`  | Illuminate + `act_scale_score_key` sheet |

`rpt_tableau__college_assessment_dashboard_benchmark_calcs` — the only place the
890 / 1010 / 1200 thresholds exist in code — reads the **official** hub only.
Practice scores do not reach it. Do not "fix" that by feeding practice in
without reading the spec: `rn_highest = 1` there would let a practice score
outrank an official one and shift reported college-ready attainment
network-wide.

## Verified facts

**`act_scale_score_key` sheet contract** — 9 columns, in this order:

`Assessment_ID`, `Academic_Year`, `Test_Type`, `Administration_Round`,
`Subject`, `Grade_Level`, `Raw_Score_Low`, `Raw_Score_High`, `Scale_Score`. All
`int64` except `Test_Type`, `Administration_Round`, `Subject`.

**Vocabulary the sheet actually uses** — not what the column names suggest:

| Column                 | Real values                                                                      | Trap                                                                                                                                              |
| ---------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Administration_Round` | `SAT1`, `SAT2`, `ACT1`                                                           | NOT `Fall`/`Winter`. Those belong to `expected_admin_season` in `expected_assessments`, a different sheet.                                        |
| `Subject`              | `Mathematics`, `Reading and Writing`, `Reading`, `Writing`, `English`, `Science` | `Mathematics`, never `Math`. The `Math` rename happens downstream.                                                                                |
| `Academic_Year`        | The "clean" year (SY26-27 = `2026`)                                              | Illuminate's raw `academic_year` is the spring year (2027). Using it is wrong.                                                                    |
| `Test_Type`            | `SAT` / `ACT`                                                                    | Stays `SAT` even when Illuminate `scope` is `Benchmark`. The sheet is the authority.                                                              |
| `Scale_Score`          | From the **`Scale Score Lower`** column of College Board's table                 | Verified: PT1 Math lower collapsed is byte-identical to assessment 138849's existing 45 rows. A perfect section therefore reads **790, not 800**. |

**`Academic_Year` is not a join key.** Both sheet joins in
`int_assessments__college_assessment_practice` are on `assessment_id` plus
`points between raw_score_low and raw_score_high` — nothing else. The model does
not project the sheet's `Academic_Year` either; the `academic_year` it outputs
comes from `int_assessments__response_rollup`. So a wrong year does **not**
break the conversion and does **not** produce a silent zero: the rows still join
and still resolve scale scores. What it does break is the year-scoped audit
query below, which stops seeing the rows, and any human trying to filter the
sheet by year. Do not describe a wrong `Academic_Year` as a join failure.

**Grade level**: sheet `Grade_Level` = Illuminate `grade_level_id` **− 1**
(verified across all 12 legacy rows: 10→9, 11→10, 12→11).

**Row shape**: one row per raw score, with `Raw_Score_Low`/`Raw_Score_High`
collapsing only where consecutive raw scores share a scale score. Collapsing is
cosmetic — `points between raw_low and raw_high` behaves identically either way,
and the legacy rows are inconsistent about it.

**Grade-11 precedent**: assessments 138849 (`Mathematics`) and 138850
(`Reading and Writing`) are the two-section digital-SAT shape, 200–790,
grade 11. Use them as the template for any new grade-11 practice SAT. They have
zero responses (created, never administered), so they are a format precedent
only.

## Procedure: Add practice assessments for a new administration

### Step 1 — get the assessments from the user

Ask for **Illuminate URLs**, one per subject per round. Preferred over raw IDs
because everything else is derivable from the assessment record:

```text
https://kippteamschools.illuminateed.com/live/?assessment_id=226184&page=Assessments_Overview_Controller#/empty
```

The `assessment_id` query parameter is the ID. If the user gives IDs instead of
URLs, also ask for the name, academic year, subject, and grade level, since you
lose the ability to cross-check the title.

### Step 2 — derive the row metadata, don't ask for it

```sql
select
  assessment_id, title, academic_year, academic_year_clean,
  scope, subject_area, grade_level_id, is_internal_assessment
from `teamster-332318.kipptaf_assessments.int_assessments__assessments_members`
where assessment_id in (<ids>)
order by assessment_id
```

Derivation rules:

| Field                  | From                                                                                                      |
| ---------------------- | --------------------------------------------------------------------------------------------------------- |
| `Assessment_ID`        | URL query param                                                                                           |
| `Academic_Year`        | `academic_year_clean`                                                                                     |
| `Test_Type`            | Title prefix (`SAT-26-27-…` → `SAT`). Never from `scope`, which reads `Benchmark`.                        |
| `Administration_Round` | Title's `BOY` → `SAT1`, `MOY` → `SAT2`                                                                    |
| `Subject`              | Title suffix mapped to sheet vocabulary: `ReadingWriting` → `Reading and Writing`, `Math` → `Mathematics` |
| `Grade_Level`          | Title's `Nth Grade`, cross-checked as `grade_level_id − 1`                                                |

Present the derived table to the user for confirmation before generating rows.
`subject_area` is frequently `null` on Reading/Writing assessments — expected,
and exactly why the sheet is authoritative.

**BOY and MOY must get different `Administration_Round` values.** The composite
branch partitions `sum(scale_score)` by `scope_round` + `administration_round`,
and the derived `administration_round` is null when `administered_at` is null.
If both rounds shared a value, a student's BOY and MOY sections would sum into
one meaningless 1600+ total.

### Step 3 — ask for the scale scores

Foundation supplies these, usually as Excel. Tell the user:

> Unhide all columns in the source tab first, then copy from Excel into Notepad,
> and paste from Notepad. Pasting straight from Excel arrives as an image, and
> hidden columns don't survive a copy at all.

**Derive the maximum raw score rather than asking for it.** Illuminate's
question metadata exists before anyone sits the test, so coverage can be checked
against an independent value instead of only against itself:

```sql
select
  assessment_id,
  count(*) as n_questions,
  sum(maximum) as total_points_possible,
  countif(is_extra_credit) as extra_credit_items
from `teamster-332318.kipptaf_illuminate.stg_illuminate__dna_assessments__fields`
where assessment_id in (<ids>)
group by 1
order by 1
```

`total_points_possible` is the value `Raw_Score_High` must reach on the top row.
Verified for the SY26-27 four: 66 / 54 / 66 / 54, matching the sheet exactly,
with no extra-credit items (when `extra_credit_items` is non-zero, decide
whether those points belong in the denominator before trusting the total).

Expect one table per subject per round. Real pastes are messy: descending sort,
headers repeated mid-stream, data rows above the header, an extra `Percentage`
column, `Scale Score Upper` present in some tabs and absent in others.

### Step 4 — generate the rows

Use [`scripts/build_scale_score_rows.py`](scripts/build_scale_score_rows.py).
Save each paste to its own `.tsv` and pass them all:

```bash
uv run python .claude/skills/carat-dashboard/scripts/build_scale_score_rows.py \
    out.tsv paste1.tsv paste2.tsv
```

It reads columns **by header name**, which is the load-bearing design choice: a
positional parser reads `Percentage` as the scale score when a tab omits
`Scale Score Upper`, and silently emits garbage. Edit the `TARGETS` list to map
assessment IDs to round + subject + source test label.

The script fails loudly on conflicting duplicate rows and reports gaps,
non-monotonic scale scores, and out-of-range values per assessment. Do not paste
anything into the sheet until every assessment reports `OK`.

### Step 5 — user pastes into the sheet

Rows append to the existing tab. There is no header in the generated output.

### Step 6 — track the rebuild in Dagster

The sheet edit is **not** visible in the warehouse until the dbt staging model
rebuilds, because it is materialized as a TABLE. There are two asset keys and
only one of them ever runs:

|              | Asset key                                                               | Behavior                                                                        |
| ------------ | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Sheet source | `kipptaf/google/sheets/kippfwd/act_scale_score_key`                     | `isMaterializable: false`, no automation condition. A stub. Never materializes. |
| dbt model    | `kipptaf/google_sheets/stg_google_sheets__kippfwd__act_scale_score_key` | What actually rebuilds. Step key `kipptaf__dbt_assets__google_sheets`.          |

```text
mcp__dagster__get_asset_materializations(
  asset_key="kipptaf/google_sheets/stg_google_sheets__kippfwd__act_scale_score_key"
)
```

**`dagster/data_version` is useless as a signal here — do not gate on it.** It
reads the same value on every materialization of this asset going back months,
including ones that demonstrably changed content. The reason is in the tags:
`dagster/input_data_version/kipptaf/google/sheets/kippfwd/act_scale_score_key`
is `INITIAL` on every run, because the sheet source is a non-observable stub
that never emits observations. The data version is therefore a hash of the code
version plus a constant, and sheet edits cannot enter it. Gating on it means
waiting forever and wrongly concluding the paste never landed.

The timestamp is also weak on its own — this asset re-materializes often
(observed three times in ~12 minutes) with no content change.

**Use BigQuery time travel to prove the rows landed**, comparing the table now
against a point before the paste:

```sql
select count(*) as rows_then
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__act_scale_score_key`
  for system_time as of timestamp('<before the paste>')
where Assessment_ID in (<ids>)
```

Zero then and non-zero now is direct evidence, independent of Dagster metadata.
Use the materialization timestamp only to corroborate _when_ it happened.

Searching for the model under a `kipptaf/google/sheets/...` prefix returns an
empty list, which reads as "no such asset" rather than "wrong key."

### Step 7 — audit before declaring it ready

Run _Procedure: Audit sheet rows_, below. Report the results to the user.

## Exception: PSAT 8/9 and PSAT 10 use official College Board tables

**Status: partially specified.** The conversion tables are understood; the
`Assessment_ID` values do not exist yet, so no rows can be finalized. Finish
this section when the assessments are created in Illuminate.

PSAT 8/9 and PSAT 10 do not follow the practice-SAT path above. They use College
Board's **official** raw-score conversion tables, which differ in three ways
that break assumptions elsewhere in this skill.

**1. The source is a PDF, not an Excel paste. Ask for the PDF link.**

> Send the link to College Board's scoring guide PDF for the practice test in
> question. Don't send a screenshot — I can only read that by eye, and there's
> no way to check the numbers afterward.

The guides are public and predictably named:

```text
https://satsuite.collegeboard.org/media/pdf/psat-8-9-practice-test-1-scoring-guide.pdf
```

Download it and extract the table programmatically. The conversion table is on
**page 5** (index 4); page 3 carries the scale definitions:

```bash
curl -sSL -o guide.pdf "<url>"
uv run --with pypdf python -c "
from pypdf import PdfReader
print(PdfReader('guide.pdf').pages[4].extract_text())
"
```

Extracted rows read `raw rw_lower rw_upper math_lower math_upper` for raws 0-54,
then `raw rw_lower rw_upper` for raws 55-66 where Math has ended. Parse by
keeping lines whose tokens are all digits, then branching on token count — 5
tokens carry both sections, 3 tokens carry Reading and Writing only.

**If a screenshot is all that exists**, transcribe it twice independently — a
second reader working blind from the same image — and diff the two. A
single-digit misread is otherwise undetectable, because every downstream check
tests internal consistency rather than fidelity to the source. Never present
transcribed-from-image numbers as verified; say they are transcribed and
unconfirmed until something independent corroborates them. Precedent: one
screenshot transcription of 122 values came back exact when later diffed against
the PDF, which proves the method can work and not that it can be trusted.

**2. Use the `LOWER` column only.** The PDF presents each section as a
`LOWER`/`UPPER` pair per raw score. Take `LOWER`, and derive
`Raw_Score_Low`/`Raw_Score_High` by collapsing runs of consecutive raw scores
that share the same `LOWER` value — the same collapse rule as the practice SAT.
Ignore `UPPER` entirely.

**3. The scale range is 120-720 per section, not 200-800.** This is the change
with teeth. Both the audit's expectations and
`scripts/build_scale_score_rows.py`'s guard
(`min(scales) < 200 or max(scales) > 800`) are hard-coded to the SAT range and
will reject valid PSAT rows. **Pending code change:** parameterize the range by
test type before running the generator for PSAT. The failure is loud rather than
silent, so it will not corrupt data — it will just block confusingly until
fixed.

**`Test_Type` values**: use `PSAT 8/9` and `PSAT10`. These match the `scope`
values already in `int_assessments__college_assessment` (verified: `PSAT 8/9`,
`PSAT10`, `PSAT NMSQT`, alongside `SAT` and `ACT`) and the `benchmark_group`
prefixes in `_benchmark_calcs` (`PSAT 8/9_...`, `PSAT10/NMSQT_...`). Do not
invent a new spelling — `_benchmark_calcs` folds `PSAT10` and `PSAT NMSQT` into
one `PSAT10/NMSQT` threshold group, so the vocabulary is load-bearing beyond
this sheet.

**Grade level**: PSAT 8/9 is grades 8-9, PSAT 10 is grade 10, which puts these
rows adjacent to the historical `× 10` rescale path. That guard is
`scope = 'SAT' and subject_area in ('Reading', 'Writing') and grade_level in (9, 10)`.
A PSAT row with `Subject = 'Reading and Writing'` does not match the subject
list, so it does not fire today — but any future change to that predicate must
not widen it to catch these.

**Verified against PSAT 8/9 Practice Test 1** (`2324-P89-773`): sections are on
a 120-720 scale, total 240-1440, Reading and Writing raw 0-66, Math raw 0-54.
Those raw maxima match Illuminate's question counts, so the usual coverage check
still applies.

**The conversion table is per practice test.** Practice Test 1 and Practice Test
2 have different tables. Establish which practice test each Illuminate
assessment corresponds to and fetch that test's PDF — the same PT1/PT2 mapping
the practice SAT needs. Never reuse one test's table for another.

**A real typo in Practice Test 1's Reading and Writing table.** Raw 65 maps to
710 and raw 66 — a perfect raw score — maps to 700, so a student answering
everything correctly reads 10 points below one who missed a question. Confirmed
against the PDF, so it is College Board's error, not a transcription slip. Treat
it as a typo: the expected correction is **720** for raw 66, which is both the
section maximum and that row's own `UPPER` value. Not yet formally decided —
confirm before entry, and record the deviation wherever the rows are documented,
since a corrected value diverges from the published table and no automated check
can detect that.

There is a second inversion in `UPPER` at raw 56-57 that does not affect us.
Both exist because, per page 3, the paper scoring method is "a simplified (and
therefore slightly less precise) version of the one used in the actual test."
Math has no inversion.

**Consequence of `LOWER` specific to PSAT**: these bands are far wider than the
practice SAT's — mean width 54 points for Reading and Writing and 51 for Math,
against roughly 20 for the SAT tables, reaching 100 points at the low end.
Taking `LOWER` therefore flattens the floor hard: Reading and Writing raws 0
through 6 all map to 120, so a student improving from 0 to 6 correct shows no
movement. This is consistent with the shipped SAT rows, which flatten raws 0-8
to 200, so `LOWER` remains the convention — but expect the question and have
this answer ready.

## Goals — sources, authoritative values, and traps

KIPP Forward owns the goals. Two source documents drive the SY26-27 rewrite:

| Document                                  | Id                                             | Owner                          |
| ----------------------------------------- | ---------------------------------------------- | ------------------------------ |
| `SY26-27 SAT Strategy` (Google Doc)       | `1FKXrTW5TY_7ORnQOvIOp4XWuUgKAi04pi0vqj2emNWs` | `kkenny@apps.teamschools.org`  |
| `SAT_GPA Goals Updated July 2026` (Sheet) | `1Mgfaxnte2M1N4_sfxhjeCe4oVpwBoaTTcSMfKXrkEuI` | `mmarrer@apps.teamschools.org` |

Neither will be shared with the ADC service account, so tab names and cell
addresses are unavailable — see `.claude/context/claude_ai_Google_Drive.md`.
**Ask which tab, or ask for a paste.** Do not report a cross-tab discrepancy
from a Drive MCP read; you cannot attribute content to a tab.

**The goals sheet contains a deprecated tab named `DO NOT USE THESE`** holding a
two-column `Class of / 1010+ SAT goal` table reading 23 / 28 / 33 percent. Those
are dead. Reading the workbook flat makes them look authoritative.

### Authoritative topline goals

Percent of students hitting the benchmark **by end of junior year**, by
graduating class. Confirmed identical in the strategy doc and the sheet's main
nine-column table:

| Class of | College Ready (1010+) | HS Grad Bar (890+) |
| -------- | --------------------- | ------------------ |
| 2027     | 22%                   | 45%                |
| 2028     | 28%                   | 55%                |
| 2029     | 34%                   | 60%                |
| 2030     | 40%                   | 70%                |
| 2031     | 47%                   | 80%                |

### Thresholds

Fourteen of the fifteen values hardcoded in
`rpt_tableau__college_assessment_dashboard_benchmark_calcs` match the strategy
doc. Two decisions have been taken:

- **`EA/ED-Ready` is retired.** The three hardcoded entries — PSAT 8/9 and
  PSAT10/NMSQT at 1100, SAT at 1200 — come out. SAT 1200 exists nowhere else, so
  check for downstream filters on that `benchmark_group` before deleting.
- **PSAT 8/9 HS-Ready is 790, not the hardcoded 800.** Fixed in the new goals
  staging sheet rather than in code, so the number becomes data.

Subject thresholds are currently split across two systems — the College-Ready
tier (EBRW 480, Math 530) lives in `_benchmark_calcs`, the grad-bar tier (EBRW
450, Math 440) lives in the goals sheet as `Board` metrics. Same concept, two
homes.

### Two dimensions the current schema cannot express

`stg_google_sheets__kippfwd__goals` has no column for either, so the SY26-27
goals are not a value-only sheet update:

- **School year.** The sheet carries `College Ready goal SY26-27` _and_
  `SY27-28` — the same goal with different percentages per year.
- **Goal horizon.** `Goals by EOY 26-27` versus `Goals by 11th grade` — an
  interim and a terminal target for the same cohort.

Also unmodelled: per-school goals arrive as free text in one cell
(`KHS: 52% NCA: 53% Lab: 69%`).

### Practice is first-class in the strategy

The strategy's third pillar commissions this work directly — track progress
"across baseline, practice and actual exams" with "group and individual" growth,
"overall and subject-specific". The testing calendar gives every grade a
`Date 1 (Practice)` and a `Date 2 (official)`. Grade 11 has **two** official
dates, so official administrations need round identity too, not just practice.

### Where the new goals tab belongs

Put it in the **existing** kippfwd workbook,
`12yqEOmyeNrvzOkmrOFnKOpsHU0L19G7zoG3b9f5cIpI`, which already backs
`act_scale_score_key` and `kippfwd goals`. It is already readable by the BigLake
connection that Sheets external tables use, so no new access has to be arranged
— a different identity again from both the Drive MCP and ADC.

Pin `sheet_range:` to the exact tab name. That is what makes a dbt source immune
to a neighbouring `DO NOT USE THESE` tab. Note the shared-trigger cost: every
Sheets source on one URI re-triggers together, so editing the goals tab also
refreshes `act_scale_score_key`.

## Procedure: Audit sheet rows after an update

Structural audit — one row per assessment, everything should be self-evident:

```sql
select
  Assessment_ID,
  count(*) as n_rows,
  count(distinct format('%T|%T|%T|%T|%T',
    Academic_Year, Test_Type, Administration_Round, Subject, Grade_Level
  )) as n_meta_combos,
  min(Raw_Score_Low) as raw_lo,
  max(Raw_Score_High) as raw_hi,
  sum(Raw_Score_High - Raw_Score_Low + 1) as raw_values_covered,
  min(Scale_Score) as scale_lo,
  max(Scale_Score) as scale_hi,
  countif(Raw_Score_Low is null or Raw_Score_High is null or Scale_Score is null)
    as null_cells
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__act_scale_score_key`
where Academic_Year = <year>
group by 1
order by 1
```

Pass criteria:

- `n_meta_combos` = 1 per assessment. More than one means a data-entry typo, and
  it will fan out the designation join in
  `int_assessments__college_assessment_practice`.
- `raw_values_covered` = `raw_hi - raw_lo + 1` **exactly**. This single identity
  catches gaps and overlaps at once: gaps make it smaller, overlaps make it
  larger. Prefer it over two separate checks.
- `raw_lo` = 0.
- `null_cells` = 0.

Continuity and monotonicity, plus a content hash:

```sql
select
  Assessment_ID,
  to_hex(md5(string_agg(
    format('%d:%d:%d', Raw_Score_Low, Raw_Score_High, Scale_Score),
    '|' order by Raw_Score_Low
  ))) as digest_md5,
  countif(prev_scale > Scale_Score) as monotonic_violations,
  countif(prev_high is not null and Raw_Score_Low != prev_high + 1)
    as discontinuities
from (
  select
    Assessment_ID, Raw_Score_Low, Raw_Score_High, Scale_Score,
    lag(Scale_Score) over (
      partition by Assessment_ID order by Raw_Score_Low
    ) as prev_scale,
    lag(Raw_Score_High) over (
      partition by Assessment_ID order by Raw_Score_Low
    ) as prev_high
  from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__act_scale_score_key`
  where Academic_Year = <year>
)
group by 1
order by 1
```

Compare `digest_md5` against the same hash computed from the source paste — this
is the only check that proves the sheet matches Foundation's data rather than
merely being internally consistent:

```bash
uv run python -c "
import hashlib, collections, sys
rows = collections.defaultdict(list)
for line in open(sys.argv[1]):
    f = line.rstrip('\n').split('\t')
    if len(f) == 9:
        rows[f[0]].append((int(f[6]), f'{f[6]}:{f[7]}:{f[8]}'))
for aid in sorted(rows):
    parts = [d for _, d in sorted(rows[aid])]
    print(aid, len(parts), hashlib.md5('|'.join(parts).encode()).hexdigest())
" out.tsv
```

Two assessments sharing a conversion table (common — BOY and MOY often reuse
one) produce identical digests. That is a valid result, not a duplication bug.

**What the audit cannot catch**: `Test_Type` is `SAT` while Illuminate `scope`
is `Benchmark`, so there is nothing to cross-check it against. A typo there
passes every check above. Eyeball those values explicitly.

## Procedure: Debug a practice score that isn't appearing

Work outward from the student, stopping at the first layer with zero rows.

1. **Does Illuminate have a session for that academic year?** This is the most
   likely cause and it is invisible from the dashboard.

   ```sql
   select academic_year, count(*) as n_sessions
   from `teamster-332318.kipptaf_illuminate.stg_illuminate__public__sessions`
   group by 1 order by 1 desc
   ```

   Practice assessments are `is_internal_assessment = false`, so they reach
   `int_assessments__scaffold` only through its
   `where not a.is_internal_assessment` branch, which inner-joins
   `int_illuminate__student_session_aff` on the **raw** `academic_year` (spring
   year — 2027 for SY26-27). If Illuminate has no sessions for that raw year,
   the assessments produce **zero rows through the entire chain** no matter how
   correct the sheet and the models are.

1. **Is the assessment in the sheet?** No sheet row means no designation, which
   means no output row.

1. **Do responses exist?** Check `int_illuminate__agg_student_responses` for the
   `assessment_id`. Zero means not yet administered or not yet synced.

1. **Did the staging model rebuild since the sheet was edited?** See Step 6
   above. The prod `stg_*` table is a frozen snapshot, never live sheet content.

1. **Is the raw score covered?** A `points` value outside every
   `Raw_Score_Low`/`Raw_Score_High` range yields a null `scale_score`.

## Gotchas that cost time

- **`__TABLES__.row_count` is unreliable and reads 0 for views.** Confirm with
  `count(*)`.
- **The BigQuery MCP service account cannot read Google Sheets externals** (no
  Drive scope). Query the materialized `stg_*` table, never the `src_*`
  external.
- **`rg -ril <pattern>` silently mangles output** — `-r` consumes `il` as a
  replacement string. Use plain `grep`.
- **`course_discipline` is `NA` on every math row** (7,397 of them). The `CASE`
  tests raw `Mathematics` while the rename to `Math` happens in a sibling column
  of the same `SELECT`, and BigQuery has no lateral column aliases. Known,
  deliberately unfixed — see the spec. Do not "fix" it incidentally; it changes
  historical values.
- **Composite rows are duplicated** — `Combined` holds 1,437 rows for 715
  student-rounds, because both composite branches are `select distinct` over
  columns that vary within the partition. Scale scores are identical across the
  duplicates and `roster_scores` takes `max`, so nothing is visibly broken. Also
  deliberately unfixed. Any new branch must stamp `course_discipline` constant
  rather than selecting it through.

## Common mistakes

| Mistake                                                                           | Consequence                                                                           |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Entering `Fall`/`Winter` in `Administration_Round`                                | Inconsistent with all 12 legacy rows; `scope_round` becomes a value nothing else uses |
| Entering `Math` instead of `Mathematics`                                          | Breaks the subject join and the total's subject count                                 |
| Using Illuminate's `academic_year` (2027) instead of `academic_year_clean` (2026) | Rows sort into the wrong year                                                         |
| Using `Scale Score Upper`                                                         | Every score inflated ~20 points against history                                       |
| Joining the sheet on `assessment_id` alone                                        | ~50× fan-out — the sheet holds 45–54 rows per assessment                              |
| Giving BOY and MOY the same round value                                           | Their sections sum into one bogus 1600+ total                                         |
| Parsing the paste by column position                                              | Reads `Percentage` as the scale score when a tab lacks `Scale Score Upper`            |
| Treating the prod `stg_*` table as current sheet content                          | Reports pre-edit values indefinitely                                                  |
| Waiting on the sheet source asset in Dagster                                      | It never materializes; you wait forever                                               |
