# QA baselines and checks

Dated prod measurements for new-data QA and refactor parity. Re-run the same
query before reusing any number; these are comparison baselines, not facts to
quote.

## Grain baselines (2026-10-02/03)

Every family model's uniqueness test grain was measured clean
(`n_rows = n_keys`) except:

- `stg_google_sheets__assessments__academic_goals` and
  `int_assessments__academic_goals`: 842 rows / 840 keys — 2 duplicated
  subject-level HS goal rows in the sheet (one AY2024, one AY2025). The warn
  tests track it; deleting the duplicate sheet rows clears it.
- `rpt_tableau__sight_words_dashboard`: ~5,500 duplicate
  `(repository_id, student_number, sight_word)` keys, all null-value on-grade
  rows, from placeholder `TBD` word fields on 6 SY21-22 quizzes (#5700; fixed in
  Illuminate, and those repositories are off the dlt sync schedule, so the
  staged copies need a manual sync after the fix).
- `rpt_tableau__assessment_dashboard`: no clean key; about 0.7% of
  `(student_number, assessment_id, response_type, response_type_code)` keys
  duplicated exactly twice (4,915 Camden / 15,590 Newark / 1,362 Paterson),
  cause untraced.

Reference sizes at measurement: `int_assessments__response_rollup` feeds ~27.5M
response rows; `fct` internal not-taken rows 76,472 (AY2025) / 64,916 (AY2026,
in progress); DDI tier roster 22,070 rows (13,086 Newark / 4,340 Camden / 3,002
Miami / 1,642 Paterson — Miami rows are expected; the extract has no region
filter and the downstream reporting sheets alias the state-proficiency column
correctly).

## After new data lands

1. The uniqueness tests run with the star tick; a new warn is the first signal.
   Compare against the exceptions above before treating one as new.
2. Pick the sample: the window's assessments are the newest `administered_at`
   rows in
   `kipptaf_google_appsheet.stg_google_appsheet__illuminate_assessments_extension`
   — take one per subject and grade band.
3. Spot-check each end to end (BigQuery MCP, read-only): the tag row above, then
   rollup rows —

   ```sql
   select response_type, count(*) as n
   from `teamster-332318`.kipptaf_assessments.int_assessments__response_rollup
   where assessment_id = <id> group by response_type
   ```

   — and table freshness via `last_modified_time` in
   `kipptaf_assessments.__TABLES__`. Rows present with the expected
   `overall`/`standard`/`group` mix passes. The full diagnosis ladder, only if a
   hop fails: [triage.md](triage.md).

4. Only when the window feeds report cards: check one published feed row against
   the mod audit sheet's `computed_avg_pct_correct`
   ([report-cards.md](report-cards.md) has the scope caveats).
5. Zero Miami rows anywhere current-year is correct; Miami rows APPEARING in a
   current year means the Focus assessment source landed — the doc's Miami
   condition then needs rewriting.

## Refactor parity

For a change that should not move values, compare per model, prod vs PR-branch
schema: `count(*)` plus the model's uniqueness-test key as
`count(distinct to_json_string(struct(<key cols>)))`, and for the dashboards a
mastery-rate aggregate by region and academic year. The grain baselines above
are the before side only if the refactor lands close to their dates; otherwise
re-measure first.
