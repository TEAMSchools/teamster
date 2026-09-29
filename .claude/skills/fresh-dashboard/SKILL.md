---
name: fresh-dashboard
description: >-
  Use when any question or task touches the FRESH enrollment recruitment
  dashboard or its lineage. Triggers: a count that doesn't match Finalsite, a
  student's status or QC flag looking wrong, reconciling goals against SRE's
  target workbook, editing the Finalsite goals, status_crosswalk or exclude_ids
  sheets, bumping finalsite_recruitment_year for a new recruitment cycle, the
  first-day-of-school dates, a new school or grade, or working on
  int_tableau__fresh_enrollment_scaffold, int_tableau__fresh_goals_scaffold,
  int_tableau__finalsite_student_scaffold,
  rpt_tableau__fresh_dashboard_progress_to_goals,
  rpt_tableau__fresh_dashboard_aggregated, rpt_tableau__fresh_dashboard_qc,
  int_finalsite__status_report_unpivot, stg_google_sheets__finalsite__goals,
  stg_google_sheets__finalsite__status_crosswalk or their upstream models.
---

# FRESH Dashboard Data Model

## Always read first

[`docs/models/fresh-dashboard-data-model.md`](../../../docs/models/fresh-dashboard-data-model.md)
is the manual for the shipped models: the spine, the goals, the actuals, each
dashboard view, the QC flags, and the known issues. Read _What is FRESH?_ and
_Data model overview_ (stop at `## Terms`) before answering anything, then the
section a route below names. This skill holds procedures and traps; it does not
repeat the doc.

## Rules for every task

- The year column is `enrollment_academic_year`, start-year form (AY2026-2027 =
  `2026`); the `rpt_tableau__fresh_dashboard_*` views alias it to
  `academic_year`. FRESH reads `var("finalsite_recruitment_year")`, not
  `current_academic_year`. Both vars are in `src/dbt/kipptaf/dbt_project.yml`.
- The scaffold is derived from the SIS and Finalsite. Nothing is hand-entered
  into it: a school or grade appears once a student is enrolled in it, or
  through `finalsite_new`, which is gated (the doc's _The three row types the
  SIS can't produce directly_).
- Miami comes from Focus (`int_focus__schools`,
  `int_focus__student_enrollment_roster`). The kipptaf PowerSchool unions carry
  no Miami rows; don't add Miami to them.
- `grade_level = -9` is a whole-school total row and `schoolid = 0` a region
  rollup (on the actuals side, "No School Assigned"). `-1` is Pre-K.
- `school_level` is banded per grade in NJ bands, so Miami grade 5 reads `MS` on
  Progress to Goals and `ES` on the goals sheet. Accepted; don't reconcile it.
- Two workbooks, never interchangeable. SRE's target workbook is the
  hand-maintained source of the numbers and is replaced every cycle. The sheet
  dbt reads is the `Finalsite` workbook, id
  `1TMkujoNxxAQw4B1hRWoIllpWZht1BAT5Wx006gXkVXU`, tab `goals`, named range
  `src_google_sheets__finalsite__goals_v2`. Say which one you mean.
- `stg_google_sheets__finalsite__goals` and
  `int_google_sheets__finalsite__goals_pivot` are tables frozen at their last
  build; only the `src_` external reads the sheet live, and the BigQuery MCP
  cannot read it (no Drive scope). Before trusting a goals comparison, check the
  `Finalsite` workbook's Drive `modifiedTime` against `last_modified_time` for
  `stg_google_sheets__finalsite__goals` in `kipptaf_google_sheets.__TABLES__`. A
  newer sheet means uningested edits: rebuild into dev first. SRE's workbook's
  `modifiedTime` answers a different question (opening it can bump it); a value
  diff is the evidence that SRE changed something.
- At the start of substantive FRESH work, and always when asked to update goals,
  ask: "Do you want to run a goals reconciliation against SRE's sheet first?"
  SRE does not always flag goal changes. If declined, goal-value discrepancies
  are out of scope.

## Route by task

| task                                                                    | read                                                                                                                  |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| A count or a student's status looks wrong (school team or engineer)     | [references/troubleshooting.md](references/troubleshooting.md)                                                        |
| Reconcile the goals sheet against SRE's workbook, paste back, gap rows  | [references/sre-workbook.md](references/sre-workbook.md), then [references/goals-sheet.md](references/goals-sheet.md) |
| Read SRE's workbook: tab maps, sourced vs derived, rounding, Sheets API | [references/sre-workbook.md](references/sre-workbook.md)                                                              |
| Map a new Finalsite status in `status_crosswalk`; add a test record id  | [references/sheet-upkeep.md](references/sheet-upkeep.md)                                                              |
| SRE's cycle rolled over: bump `finalsite_recruitment_year`              | [references/recruitment-year-rollover.md](references/recruitment-year-rollover.md)                                    |
| QC worklist flags, first-day-of-school dates, `is_enrolled_fdos`        | [references/qc-worklist.md](references/qc-worklist.md)                                                                |
| What a model, column or goal means                                      | the doc section for it                                                                                                |

## Why did this number change

| symptom                                                 | usual cause                                                                                 | where                           |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------- |
| A whole status category is missing for a school or year | a `(detailed_status, enrollment_type)` pair missing from `status_crosswalk` for that key    | troubleshooting, check 1        |
| Everything went empty after a rollover                  | `status_crosswalk` column A still holds the old `_dagster_partition_key`                    | rollover, step 0d               |
| One student shows the wrong latest status               | two statuses set the same day in Finalsite                                                  | troubleshooting, Reset Protocol |
| Counts are inflated                                     | a test record not yet in `exclude_ids`                                                      | sheet-upkeep                    |
| A goal doesn't match what was just typed into the sheet | the goals tables are frozen until rebuilt                                                   | rules above                     |
| A grade being recruited for has no row and no goals     | `finalsite_new` is closed while `finalsite_recruitment_year` equals `current_academic_year` | doc, _The three row types..._   |
| SIS columns and comparison flags went NULL network-wide | the recruitment year is ahead of the SIS year                                               | doc, _Known data model caveats_ |
| PowerSchool says N, the dashboard says fewer            | students with no Finalsite record (`is_missing_finalsite_record`)                           | qc-worklist                     |

## Sheet handoff contract

Claude does not write to the goals, crosswalk or exclude-ids sheets. It hands
the analyst a paste block: every row the tab should contain, tab-delimited, in
the sheet's column order, one fenced block, pasted at `A2` (row 1 is the header,
`skip_leading_rows: 1`). Build it from the current staging rows plus only the
changes you can attribute to a source cell, diff it against staging on row count
and key set before handing it over, and name each change in prose with its
source cell. After the paste, rebuild the consumers and confirm the change
reached the table before saying it's done. Details:
[references/goals-sheet.md](references/goals-sheet.md), the loop's _Hand back a
FULL rebuild_ step.

## Scripts

None. The queries live in the references; they cannot read `{{ var(...) }}`, so
substitute the year by hand.
