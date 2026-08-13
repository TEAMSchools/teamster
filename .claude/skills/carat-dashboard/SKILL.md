---
name: carat-dashboard
description: >-
  Use when any question or task touches the CARAT dashboard (College Admission
  Readiness Assessments Tracker) or its lineage. Triggers: adding Illuminate
  practice SAT/ACT assessments for a new administration, generating or auditing
  raw-to-scale-score rows for the practice conversion or scaffold sheets, a
  practice score not appearing on the dashboard, goal thresholds not matching,
  academic-year rollover, or working on
  int_assessments__college_assessment_practice,
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

| Pipeline | Hub model                                      | `test_type` | Source                                        |
| -------- | ---------------------------------------------- | ----------- | --------------------------------------------- |
| Official | `int_assessments__college_assessment`          | `Official`  | kippadb + collegeboard                        |
| Practice | `int_assessments__college_assessment_practice` | `Practice`  | Illuminate + the conversion and scaffold tabs |

Both pipelines meet in `int_assessments__all_college_assessments`, and
`rpt_tableau__college_assessment_dashboard_benchmark_calcs` reads that hub.
Thresholds are no longer hardcoded — they come from the scaffold sheet's
`hs_ready_min_score` / `college_ready_min_score`, and `EA/ED-Ready` is retired.

Practice **does** reach the benchmark view now, and what makes that safe is
`test_type` sitting in the partition of both
`rn_highest_benchmark_aligned_scope` and `benchmark_aligned_scope_max_score`.
Never remove it. Without it a practice score competes with an official one, can
win, and shifts reported college-ready attainment network-wide. The view also
joins `expected_test_type` to the hub's `test_type`, so a practice benchmark is
never satisfied by an official result.

## Verified facts

### Two tabs, not one

Practice entry touches **two** tabs in the CARAT workbook
(`12yqEOmyeNrvzOkmrOFnKOpsHU0L19G7zoG3b9f5cIpI`). Putting a value in the wrong
one is the most common way to waste an hour:

| Tab                      | Model                                                         | Holds                                                          |
| ------------------------ | ------------------------------------------------------------- | -------------------------------------------------------------- |
| `Scale Score Conversion` | `stg_google_sheets__kippfwd__practice_scale_score_conversion` | raw-to-scale bands, one row per band per assessment            |
| `Scaffold`               | `stg_google_sheets__kippfwd__scaffold`                        | vocabulary — subject alignments, course discipline, cut scores |

Rule: a value that repeats across every band of an assessment is vocabulary and
belongs in `Scaffold`. A value that varies band to band belongs in
`Scale Score Conversion`. **`score_type` lives in both** — it is the join key,
and the only column spelled identically on each side.

`ACT Scale Score Key V1` is the superseded tab, still read by production until
this work merges. Do not enter new rows there.

**Conversion tab contract** — 12 columns, in this order, all `int64` except
`scope`, `scope_round`, `subject`, `score_type`:

`assessment_id`, `academic_year`, `scope`, `scope_round`, `subject`,
`grade_level`, `raw_score_low`, `raw_score_high`, `scale_score`,
`aligned_scale_score`, `score_type`, `expected_total_subjects_tested`.

The headers are lowercase snake_case. `scope` and `scope_round` were renamed
from `Test_Type` and `Administration_Round`; the column ORDER did not change, so
the row generator still emits pasteable output unchanged. Because the external
declares `skip_leading_rows: 1`, columns map POSITIONALLY from the dbt
`columns:` list — the sheet header is ignored, so renaming a header needs no
coordinated dbt change, and reordering the sheet silently corrupts every row.

**Vocabulary the conversion tab actually uses** — not what the column names
suggest:

| Column                | Real values                                                                      | Trap                                                                                                                                                     |
| --------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scope_round`         | `SAT1`, `SAT2`, `ACT1`, `PSAT891`, `PSAT101`                                     | NOT `Fall`/`Winter`. Those belong to `expected_admin_season` in `expected_assessments`, a different sheet. No underscore, and PSAT keeps a trailing `1`. |
| `subject`             | `Mathematics`, `Reading and Writing`, `Reading`, `Writing`, `English`, `Science` | `Mathematics`, never `Math`. The scaffold holds the `Math` spelling.                                                                                     |
| `academic_year`       | The "clean" year (SY26-27 = `2026`)                                              | Illuminate's raw `academic_year` is the spring year (2027). Using it is wrong.                                                                           |
| `scope`               | `SAT`, `ACT`, `PSAT 8/9`, `PSAT10`                                               | The real test, even when Illuminate's own scope reads `Benchmark` or null. The sheet is the authority. `PSAT10` has no space.                            |
| `scale_score`         | From the **`Scale Score Lower`** column of College Board's table                 | A perfect section therefore reads **790, not 800** on the digital SAT.                                                                                   |
| `aligned_scale_score` | `scale_score`, except ×10 on grade 9-10 SAT Reading and Writing                  | Those are legacy 10-40 test scores, not 200-800 section scores. The model reads this column and does no rescaling of its own.                            |
| `score_type`          | Must exist in `int_kippadb__standardized_test_unpivot` or the official hub       | Invented values join to nothing. There is no `sat_writing` with data and no `act_writing` at all.                                                        |

**`academic_year` IS a join key now.** The conversion-to-scaffold join is on
(`academic_year`, `scope` = `expected_scope`, `score_type` =
`expected_score_type`). A wrong year silently drops every band for that
assessment, because the join is inner. This changed — older notes saying
`Academic_Year` is not a join key describe the superseded model.

**Grade level**: conversion `grade_level` = Illuminate `grade_level_id` **− 1**
(verified across all 12 legacy rows: 10→9, 11→10, 12→11). It is deliberately NOT
part of the scaffold join — see _Procedure: Add scaffold rows_.

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

| Field           | From                                                                                                      |
| --------------- | --------------------------------------------------------------------------------------------------------- |
| `Assessment_ID` | URL query param                                                                                           |
| `Academic_Year` | `academic_year_clean`                                                                                     |
| `scope`         | Title prefix (`SAT-26-27-…` → `SAT`). Never from Illuminate's own scope, which reads `Benchmark`.         |
| `scope_round`   | Title's `BOY` → `SAT1`, `MOY` → `SAT2`                                                                    |
| `Subject`       | Title suffix mapped to sheet vocabulary: `ReadingWriting` → `Reading and Writing`, `Math` → `Mathematics` |
| `Grade_Level`   | Title's `Nth Grade`, cross-checked as `grade_level_id − 1`                                                |

Present the derived table to the user for confirmation before generating rows.
`subject_area` is frequently `null` on Reading/Writing assessments — expected,
and exactly why the sheet is authoritative.

**BOY and MOY must get different `scope_round` values.** The total branch
partitions `sum(scale_score)` by `scope_round`, and nothing else distinguishes
the two rounds — the hub's `administration_round` is derived from Illuminate's
`administered_at`, which is null on every externally created assessment. If both
rounds shared a value, a student's BOY and MOY sections would sum into one
meaningless 1600+ total.

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

|              | Asset key                                                                           | Behavior                                                                        |
| ------------ | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Sheet source | `kipptaf/google/sheets/kippfwd/practice_scale_score_conversion`                     | `isMaterializable: false`, no automation condition. A stub. Never materializes. |
| dbt model    | `kipptaf/google_sheets/stg_google_sheets__kippfwd__practice_scale_score_conversion` | What actually rebuilds. Step key `kipptaf__dbt_assets__google_sheets`.          |

```text
mcp__dagster__get_asset_materializations(
  asset_key="kipptaf/google_sheets/stg_google_sheets__kippfwd__practice_scale_score_conversion"
)
```

**`dagster/data_version` is useless as a signal here — do not gate on it.** It
reads the same value on every materialization of this asset going back months,
including ones that demonstrably changed content. The reason is in the tags:
`dagster/input_data_version/kipptaf/google/sheets/kippfwd/practice_scale_score_conversion`
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
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__practice_scale_score_conversion`
  for system_time as of timestamp('<before the paste>')
where Assessment_ID in (<ids>)
```

Zero then and non-zero now is direct evidence, independent of Dagster metadata.
Use the materialization timestamp only to corroborate _when_ it happened.

Searching for the model under a `kipptaf/google/sheets/...` prefix returns an
empty list, which reads as "no such asset" rather than "wrong key."

### Step 7 — add the scaffold rows

Run _Procedure: Add scaffold rows_, below. Conversion bands with no matching
scaffold row are dropped silently by the model's inner join, so this step is not
optional.

### Step 8 — audit before declaring it ready

Run _Procedure: Audit sheet rows_, below. Report the results to the user.

## Procedure: Add scaffold rows

One row per section **plus one per total**, per administration. Derive them from
the conversion tab rather than authoring by hand — the conversion rows already
carry the test type, grade, subject, and score type.

### Step 1 — find what is missing

```sql
with conv as (
  select distinct academic_year, scope, grade_level, subject, score_type
  from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__practice_scale_score_conversion`
),
scaf as (
  select distinct academic_year, expected_scope, expected_score_type
  from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__scaffold`
  where expected_test_type = 'Practice'
)
select c.*, if(s.expected_score_type is null, 'MISSING', 'present') as status
from conv as c
left join scaf as s
  on c.academic_year = s.academic_year
  and c.scope = s.expected_scope
  and c.score_type = s.expected_score_type
order by status desc, 1, 2, 3
```

This finds section rows only. Total rows have no conversion counterpart, so
check separately that each (`academic_year`, `scope`) has a row with
`expected_grouping = 'Total'` — `act_composite`, `sat_total_score`,
`psat89_total`, `psat10_total`.

### Step 2 — take vocabulary from an existing row of the same score type

Values are constant per `score_type` across years and test types, so copy them
rather than deriving. Thresholds especially: `hs_ready_min_score` and
`college_ready_min_score` are per score type, and four score types legitimately
have none anywhere — `act_english`, `act_science`, `sat_reading_test_score`,
`sat_writing_and_language_test_score`.

```sql
select distinct
  expected_score_type, expected_practice_test_subject, expected_subject_area,
  expected_aligned_subject_area, expected_grouping, expected_course_discipline,
  expected_score_category, hs_ready_min_score, college_ready_min_score
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__scaffold`
order by expected_score_type
```

### Step 3 — emit rows in sheet column order

17 columns: `academic_year`, `expected_aligned_test_type`, `expected_test_type`,
`expected_grade_level`, `expected_scope`, `expected_aligned_scope`,
`expected_practice_test_subject`, `expected_subject_area`,
`expected_aligned_subject_area`, `expected_grouping`,
`expected_course_discipline`, `expected_score_category`, `expected_score_type`,
`a1_attempt_min_score`, `a2_plus_attempts_min_score`, `hs_ready_min_score`,
`college_ready_min_score`.

Emit **without a header row** — rows append to the existing tab.

On total rows: `expected_practice_test_subject` and `expected_subject_area` are
`Composite` for ACT and `Combined` for everything else,
`expected_aligned_subject_area` and `expected_grouping` are `Total`, and
`expected_course_discipline` is `NA`.

### Step 4 — check the grain before pasting

The uniqueness key is (`academic_year`, `expected_test_type`, `expected_scope`,
`expected_grade_level`, `expected_score_type`). **`expected_grade_level` is in
the key for a reason**: AY2023 ran two SAT forms at once, a three-section form
for grades 9-10 and the two-section digital form for grade 11, so `sat_math` and
`sat_total_score` each appear twice that year differing only in grade.

That is also why the model's join deliberately omits grade and uses
`select distinct` to collapse the pair — the vocabulary is identical, only the
grade differs. If a future administration needs _different_ vocabulary per
grade, that `distinct` breaks quietly and the join needs the grade split
instead.

## Exception: PSAT 8/9 and PSAT 10 use official College Board tables

**Status: shipped for SY26-27.** 181 rows entered and audited clean (every
digest matches source). Use these as the format precedent:

| `assessment_id` | `scope`    | `scope_round` | `subject`           | `grade_level` | Rows | Raw  | Scale   |
| --------------- | ---------- | ------------- | ------------------- | ------------- | ---- | ---- | ------- |
| 226308          | `PSAT 8/9` | `PSAT891`     | Reading and Writing | 9             | 50   | 0-66 | 120-720 |
| 226309          | `PSAT 8/9` | `PSAT891`     | Mathematics         | 9             | 42   | 0-54 | 120-690 |
| 226310          | `PSAT10`   | `PSAT101`     | Reading and Writing | 10            | 49   | 0-66 | 160-760 |
| 226311          | `PSAT10`   | `PSAT101`     | Mathematics         | 10            | 40   | 0-54 | 160-760 |

`scope_round` has no underscore and keeps a trailing `1` — user's call, so do
not "normalize" it. The `1` leaves room for a second practice administration in
the same grade and year, which would otherwise sum into one bogus total (see the
BOY/MOY warning above).

**Outstanding verification on 226310 / 226311.** Illuminate syncs once nightly,
and these two were created after that run, so at entry time they were absent
from the warehouse — the question-count coverage check in Step 3 could not run,
and which ID holds which subject came from the user rather than from `title`.
226308 / 226309 did check out (66 and 54, matching the guide exactly). Confirm
226310 has 66 questions and 226311 has 54 once they land; a mismatch means the
wrong practice form or swapped subjects, and no other check will catch it.

PSAT 8/9 and PSAT 10 do not follow the practice-SAT path above. They use College
Board's **official** raw-score conversion tables, which differ in four ways that
break assumptions elsewhere in this skill.

**1. The source is a PDF, not an Excel paste. Ask for the PDF link.**

> Send the link to College Board's scoring guide PDF for the practice test in
> question. Don't send a screenshot — I can only read that by eye, and there's
> no way to check the numbers afterward.

The guides are public and predictably named:

```text
https://satsuite.collegeboard.org/media/pdf/psat-8-9-practice-test-1-scoring-guide.pdf
```

Download it and extract the table programmatically. **The page index differs per
guide** — PSAT 8/9 puts the conversion table on page 5 (index 4), PSAT/NMSQT on
page 6 (index 5). Locate it rather than assuming; the page carrying the scale
definitions is two before it.

**Extract by word COORDINATES, not `extract_text()`.** The table is laid out as
two side-by-side column-blocks (raws 0-33 left, 34-66 right). Flat text
extraction interleaves them, which produced a table that looked plausible and
was wrong — it manufactured phantom non-monotonic rows around raw 56 that do not
exist in the PDF. Group words into visual rows by `top`, split each row on an
x-coordinate threshold (~300 on a 612pt-wide page), then read each block
separately:

```bash
curl -sSL -o guide.pdf "<url>"
uv run --with pdfplumber python -c "
import pdfplumber
with pdfplumber.open('guide.pdf') as pdf:
    for w in pdf.pages[4].extract_words():
        if w['text'].strip().isdigit():
            print(w['text'], round(w['x0']), round(w['top']))
"
```

Within a block, rows read `raw rw_lower rw_upper math_lower math_upper` while
both sections are live, then `raw rw_lower rw_upper` past Math's maximum. Branch
on token count — 5 tokens carry both sections, 3 tokens carry Reading and
Writing only.

**Confirm anything surprising by rendering the region as an image** and reading
it. `page.crop(box).to_image(resolution=300).save(...)` settles a
source-anomaly-versus-parser-bug question in one step, and two text parses
agreeing is not proof — they can share the same layout misreading.

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

**3. The two PSATs are on DIFFERENT scales.** This is the one with teeth:

| Test                | Section scale | Total    |
| ------------------- | ------------- | -------- |
| SAT                 | 200-800       | 400-1600 |
| PSAT 8/9            | 120-720       | 240-1440 |
| PSAT 10, PSAT/NMSQT | 160-760       | 320-1520 |

Do not carry one PSAT bound across both — a PSAT 10 row checked against 120-720
is 40 points out of range at each end and still passes. `SCALE_RANGE` in
`scripts/build_scale_score_rows.py` is keyed by the test label for exactly this
(the script still calls that field `Test_Type` internally); add an entry rather
than widening one.

**PSAT 10 has no separate scoring guide.** College Board publishes one practice
form for PSAT/NMSQT and PSAT 10 (same 160-760 scale), so the PSAT/NMSQT guide is
the source for PSAT 10 rows. Nothing in the document says "PSAT 10" — say so
plainly when reporting, and confirm the Illuminate assessment was built from
that same form before trusting the conversion.

**`scope` values**: use `PSAT 8/9` and `PSAT10`. These match the `scope` values
already in `int_assessments__college_assessment` (verified: `PSAT 8/9`,
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

**4. A real typo in PSAT 8/9 Practice Test 1's Reading and Writing table, and
the one sanctioned deviation from a published table.** Raw 65 maps to 710 and
raw 66 — a perfect raw score — maps to 700, so a student answering everything
correctly would read 10 points below one who missed a question. Confirmed
against the rendered PDF, so it is College Board's error, not a transcription
slip.

**Decided and shipped: raw 66 is entered as 720** for assessment 226308, which
is both the section maximum and that row's own `UPPER` value. This is the only
place the sheet knowingly diverges from a published table.

The correction lives in `SCALE_CORRECTIONS` in the generator, not as an
exemption from the monotonic check — the check stays fatal, because its real job
is catching column misalignment during parsing, and a quiet exemption would
retire a working guard to accommodate one bad cell. The generator prints every
correction it applies and aborts on a stale entry (one naming a raw score that
is absent, or one the source now already agrees with).

**No downstream check can detect a corrected value**, which is why it is
recorded here, in the reference doc, and in the generator's comments.

There is a second inversion in `UPPER` at raw 56-57 that does not affect us.
Both exist because, per the guide's own scale-definition page, the paper scoring
method is "a simplified (and therefore slightly less precise) version of the one
used in the actual test." Math has no inversion.

**PSAT 8/9 cannot reach its scale maximum**, typo aside: Reading and Writing
tops out at 710 and Math at 690, so a perfect raw score converts to 1400 (1410
with the correction), not 1440. Published behavior, not an entry error. Both
PSAT 10 sections do reach 760, so PSAT 10 does reach 1520.

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

### The rebuilt goals tab — what shipped

The sheet was rebuilt on named range `src_google_sheets__kippfwd_goals_v3`, nine
columns:

```text
academic_year, test_type, grade_level, cohort, score_type,
pct_1_attempt, pct_2_plus_attempts, pct_hs_ready, pct_college_ready
```

Staging unpivots the four percentage columns to long, so a metric is a row
rather than a column. Ten sheet rows become 34, not 40 — UNPIVOT drops nulls,
and every PSAT row is blank for `pct_2_plus_attempts`.

Three things this resolved, all previously listed here as unmodellable:

- **School year** is now `academic_year`, a real column.
- **Thresholds left the goals sheet entirely.** They live on the scaffold as
  `a1_attempt_min_score`, `a2_plus_attempts_min_score`, `hs_ready_min_score`,
  `college_ready_min_score`. `min_score` no longer means an attempt count on one
  row and a scale score on the next.
- **Region and school differentiators are gone**, not null — KIPP Forward
  stopped setting goals that way, so the free-text per-school cell has no
  successor.

`int_google_sheets__kippfwd__goals_unpivot` joins goals to scaffold and is what
consumers should read. Goal horizon (interim versus terminal for one cohort) is
still unmodelled; every current row is AY2026.

Declare `grade_level` and `cohort` as STRING in the source. The scaffold's
`expected_grade_level` holds comma-separated lists, and INT64 would foreclose
the same on the goals side while needing a sheet-coordinated external rebuild to
undo.

### Practice is first-class in the strategy

The strategy's third pillar commissions this work directly — track progress
"across baseline, practice and actual exams" with "group and individual" growth,
"overall and subject-specific". The testing calendar gives every grade a
`Date 1 (Practice)` and a `Date 2 (official)`. Grade 11 has **two** official
dates, so official administrations need round identity too, not just practice.

### Counting attempts — use the hub, never `count(*)`

`int_assessments__all_college_assessments` carries `attempt_lifetime` and
`yearly_attempts_totals`. Both count **distinct `test_date`**, on total rows
only, partitioned by `test_type`. Read those rather than counting rows anywhere.

`count(*)` is wrong on this data: 261 official sittings hold the same score
twice under different `rn_highest` values, so a row count credits one sitting as
two attempts. `dense_rank` on `test_date` is what makes the fix work — duplicate
dates share a rank, so the max of the rank is the distinct-date count.
`row_number` would not.

Section rows read null on both fields by design. An attempt is counted once per
sitting, not once per section sat.

`int_students__college_assessment_participation_roster` reads these rather than
deriving counts. Its grain now includes `test_type`, so **filter `test_type` as
well as `rn_lifetime = 1`** — a student with practice data returns one row of
each.

### Hunting duplicates in kippadb — key on subject

If you check `stg_kippadb__standardized_test` for duplicate records, the key
must be contact, date, test type **and subject**. Without subject, 1,548
students who legitimately sit several AP exams on one day read as 2,289
duplicates, and a delete list built from that would destroy real records.

Fingerprint every non-identity column, not just the score fields, before calling
a pair redundant — two records can share a score and differ on
`administration_round` or `scoring_irregularity`.

Verified real duplicates as of 2026-08: 87 ACT/SAT records (86 of them Camden
class of 2027 on the April 2026 school-day SAT) and 478 PSAT records from 2024.
One 2015 SAT pair has genuinely different scores and is not a duplicate.

### Where the new goals tab belongs

Put it in the **existing** kippfwd workbook,
`12yqEOmyeNrvzOkmrOFnKOpsHU0L19G7zoG3b9f5cIpI`, which already backs
`Scale Score Conversion`, `Scaffold`, and `Goals`. It is already readable by the
BigLake connection that Sheets external tables use, so no new access has to be
arranged — a different identity again from both the Drive MCP and ADC.

Pin `sheet_range:` to the exact tab name. That is what makes a dbt source immune
to a neighbouring `DO NOT USE THESE` tab. Note the shared-trigger cost: every
Sheets source on one URI re-triggers together, so editing the goals tab also
refreshes the conversion and scaffold tabs.

## Procedure: Audit sheet rows after an update

Structural audit — one row per assessment, everything should be self-evident:

```sql
select
  Assessment_ID,
  count(*) as n_rows,
  count(distinct format('%T|%T|%T|%T|%T',
    academic_year, scope, scope_round, subject, grade_level
  )) as n_meta_combos,
  min(Raw_Score_Low) as raw_lo,
  max(Raw_Score_High) as raw_hi,
  sum(Raw_Score_High - Raw_Score_Low + 1) as raw_values_covered,
  min(Scale_Score) as scale_lo,
  max(Scale_Score) as scale_hi,
  countif(Raw_Score_Low is null or Raw_Score_High is null or Scale_Score is null)
    as null_cells
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__practice_scale_score_conversion`
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
  from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__practice_scale_score_conversion`
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

**What the audit cannot catch**: the sheet's `scope` is authoritative and
Illuminate's own scope disagrees by design, so there is nothing to cross-check
it against. A typo there passes every check above. Eyeball those values
explicitly.

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
- **`WHERE` runs before window functions.** Section rows borrow their score from
  the `overall` sibling via
  `max(if(response_type = 'overall', …)) over (partition by … assessment_id)`,
  and that window must live in the `responses` CTE where both row types exist.
  Computing it in a select that already filters `where response_type = 'Group'`
  returns null on every row, silently — the condition is never true over the
  surviving partition.
- **`scope` now comes from the sheet, not Illuminate.** The hub's `scope` is the
  real test and `test_type` is the constant `Practice`, matching the official
  hub. Illuminate's own scope — `SAT`/`ACT` on AY2023 rows, `Benchmark` on the
  SY26-27 SAT assessments, null on the PSATs — is never read. Every predicate
  selecting a test keys on `scope`; keying on `test_type` matches nothing and
  fails silently.
- **`grouping` is a BigQuery reserved word** (`GROUPING SETS`). Aliasing the
  scaffold's `expected_grouping` to `grouping` needs backticks.
- **Two defects are now FIXED** — do not re-flag them from older notes.
  `course_discipline` no longer reads `NA` on math rows (it comes from the
  scaffold, and Math is `MATH`, Science `SCI`), and composite rows are no longer
  duplicated (the composite is built with `group by`, so ACT is 1:1 at 379 rows
  where production had 1,094). Both changes are documented in the reference
  doc's impact section.
- **AY2023 grade 9-10 SAT is excluded on purpose — do not re-add it.** KIPP
  Forward ruled those administrations invalid (grades 9-10 should have sat PSAT,
  not a full SAT form). The exclusion lives in the scaffold sheet: all three
  AY2023 SAT Practice rows were deleted (`sat_math`, `sat_ebrw`,
  `sat_total_score`), so the conversion CTE's inner join drops every band. Their
  conversion bands are still in the sheet and are inert. Deleting `sat_math` was
  safe only because grade 11 AY2023 has no data at all — 138849 and 138850
  return zero rows from every Illuminate layer. AY2023 ACT stays and still
  reports 379 composites.
- **`rpt_tableau__college_assessment_dashboard_scores` averages over ALL
  attempts under both Score Category options — that is the design, not a bug.**
  The filter switches the measure between `scale_score` (each attempt's own
  score) and `max_scale_score` (that student's best for the score type); both
  average over the same row set, so a student who tested twice counts twice
  either way. It looks like an attempt-weighting error and it is not. Do not
  "correct" it by filtering `rn_highest = 1` — that would empty the
  `scale_score` option, whose entire purpose is showing every attempt. The
  view's grain is one row per attempt and both measures share it.
- **Deleting a scaffold row is the exclusion mechanism, and it is grade-blind.**
  The conversion-to-scaffold join keys on (`academic_year`, `scope`,
  `score_type`) and deliberately omits grade, so a score type shared across
  grades cannot be excluded for one grade only. A first attempt at the AY2023
  exclusion removed Reading and Writing but left `sat_math`, which grade 11 also
  uses — leaving 737 Total rows with `actual_total_subjects_tested = 1` against
  `expected = 3` and a null score on every one.

## Common mistakes

| Mistake                                                                           | Consequence                                                                           |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Entering `Fall`/`Winter` in `scope_round`                                         | Inconsistent with all 12 legacy rows; `scope_round` becomes a value nothing else uses |
| Entering `Math` instead of `Mathematics`                                          | Breaks the subject join and the total's subject count                                 |
| Using Illuminate's `academic_year` (2027) instead of `academic_year_clean` (2026) | Rows sort into the wrong year                                                         |
| Using `Scale Score Upper`                                                         | Every score inflated ~20 points against history                                       |
| Joining the sheet on `assessment_id` alone                                        | ~50× fan-out — the sheet holds 45–54 rows per assessment                              |
| Giving BOY and MOY the same round value                                           | Their sections sum into one bogus 1600+ total                                         |
| Parsing the paste by column position                                              | Reads `Percentage` as the scale score when a tab lacks `Scale Score Upper`            |
| Treating the prod `stg_*` table as current sheet content                          | Reports pre-edit values indefinitely                                                  |
| Waiting on the sheet source asset in Dagster                                      | It never materializes; you wait forever                                               |
