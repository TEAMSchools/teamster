# Triage

For "my assessment/scores are not on the dashboard," worksheet disagreements,
wrong teacher/section, access problems, and the manual refresh push. Run the
ladder in order; most cases end at step 1.

## The missing-data ladder

1. **Tag.** Query the extension table for the assessment (by id from the
   Illuminate URL, or title):

   ```sql
   select assessment_id, module_type, module_sequence, administered_at,
       regions_assessed, regions_report_card, regions_progress_report
   from `teamster-332318`.kipptaf_google_appsheet.stg_google_appsheet__illuminate_assessments_extension
   where assessment_id = <id>
   ```

   No row — it is untagged and invisible to DKI/Module Dashboard, the feeds, and
   the star. Wrong `administered_at` — it lands in the wrong week/term. Missing
   region in `regions_assessed` — that region's students are never expected to
   take it. Grade or module wrong — canonical grouping breaks
   ([tagging.md](tagging.md)).

2. **Illuminate landed it.** The assessment tables sync at 00:00 and 17:00
   daily, plus Wed 10:00/14:00 and Fri 15:00 (Eastern); reference tables (bands,
   reporting groups) at 00:00 only. Check
   `int_illuminate__agg_student_responses` for the `assessment_id`; if absent
   but present in Illuminate, the next sync carries it.

3. **The star ticked.** `int_assessments__response_rollup` (and the table
   intermediates and marts) rebuild at 00:00, 10:00, 13:00, 15:00, 17:00. The
   00:00/17:00 ticks race the sync — same-hour data can wait for the next tick.
   Check `last_modified_time` in `kipptaf_assessments.__TABLES__`, then confirm
   the rows:

   ```sql
   select response_type, count(*) as n
   from `teamster-332318`.kipptaf_assessments.int_assessments__response_rollup
   where assessment_id = <id> group by response_type
   ```

4. **Tableau refreshed.** The DDI Suite extracts refresh at 01:00 and 18:00
   daily plus Friday 16:00 (exposure `ddi_suite`). Rows in the extract view but
   not the workbook means the workbook is waiting on the next refresh.

If the tag is right and the rollup rows exist, the cause is on the data side —
confirm extract rows before and after a refresh rather than re-arguing the tag.

One build-stopping case: the AppSheet extension table and the standard-domains
sheet carry error-severity uniqueness tests, so a duplicate AppSheet row or a
duplicate pasted domains row fails the staging build and the whole star tick
skips — everything goes stale at once. Check dbt test failures when every
consumer is stale together.

## Manual refresh push

After a tag fix, users expect a push rather than the next tick. In order, via
Dagster (mutation tools preview with `confirm=False` first; data team runs
them):

1. Materialize the star tick's table assets — at minimum
   `int_assessments__response_rollup` (its dbt asset under the kipptaf code
   location); include `int_assessments__scaffold` when expectations changed (new
   tag, date, or region).
2. Once those runs finish, materialize the `ddi_suite` Tableau refresh asset
   (exposure asset, workbook LSID `6d82b643-59a8-4106-b2f9-97ddf7f638e7`).

The DeansList feeds need no push — they deliver at 01:25 nightly.

## Two worksheets disagree

Denominator questions, not defects, in this order:

- **Not-taken rows.** A null `response_type` row (null `date_taken`) is
  assigned-but-not-taken. Mastery cuts exclude them; completion cuts include
  them. (PR #3576, open, proposes an `is_completion_row` flag.)
- **Population cut.** Course-enrollment cuts put an Algebra 1 8th grader in
  Algebra; grade-level cuts put them in grade 8.
- **Multi-assessment DKI cut.** Quizzes tagged to different dates per grade
  level make a combined table ragged — view by grade level.
- **Dashboard vs Illuminate.** Reconcile against the extract rows (step 3 query)
  and, for the report-card feeds, the mod audit sheet
  ([report-cards.md](report-cards.md)).

## Wrong or missing teacher/section

- The course join keeps one section per student, year and subject
  (`rn_student_year_illuminate_subject_desc = 1`): honors and second sections
  drop from classroom rollups, and a co-teacher or interventionist can be the
  section of record. Model behavior, not a data error.
- A wrong course assignment in PowerSchool rolls students up under the wrong
  course. Fix in PowerSchool; it populates on the next morning's refresh.

## Access

A blank DDI Suite page from the Launch page, or a login failure, is Tableau
licensing or permissions. Route to the Tableau admin path; read no SQL.
