# Practice assessments — conversion and scaffold tabs, entry, audit, debug

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
part of the scaffold join — see _Procedure: Add scaffold rows_ below.

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

Use [`scripts/build_scale_score_rows.py`](../scripts/build_scale_score_rows.py).
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

Run _Procedure: Add scaffold rows_ below. Conversion bands with no matching
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
rather than deriving. Thresholds especially: `hs_grad_ready_min_score` and
`college_ready_min_score` are per score type, and four score types legitimately
have none anywhere — `act_english`, `act_science`, `sat_reading_test_score`,
`sat_writing_and_language_test_score`.

```sql
select distinct
  expected_score_type, expected_practice_test_subject, expected_subject_area,
  expected_aligned_subject_area, expected_grouping, expected_course_discipline,
  expected_score_category, hs_grad_ready_min_score, college_ready_min_score
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__kippfwd__scaffold`
order by expected_score_type
```

### Step 3 — emit rows in sheet column order

17 columns: `academic_year`, `expected_aligned_test_type`, `expected_test_type`,
`expected_grade_level`, `expected_scope`, `expected_aligned_scope`,
`expected_practice_test_subject`, `expected_subject_area`,
`expected_aligned_subject_area`, `expected_grouping`,
`expected_course_discipline`, `expected_score_category`, `expected_score_type`,
`a1_attempt_min_score`, `a2_plus_attempts_min_score`, `hs_grad_ready_min_score`,
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
