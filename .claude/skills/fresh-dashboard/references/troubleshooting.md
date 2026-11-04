# Troubleshooting a count or a status

## For a non-engineer: "why does this number look wrong?"

Start here if you're on the school or enrollment team, not an engineer.

1. **Is the whole school or region off, or one specific student?**
   - Whole category (for example all Inquiries for a school): likely a
     `status_crosswalk` mapping gap. Ask an engineer to run check 1 below.
   - One student showing the wrong status: check the FRESH Dashboard's Progress
     to Goals tab, **OPEN ROSTER** button (top right), for that student's
     current status. If it looks wrong and two statuses were set on the same day
     in Finalsite, use the Reset Protocol:
     1. Put them in another status.
     2. Wait a day.
     3. Put them in the status you want.
   - Numbers look inflated: a test or fake Finalsite record may need adding to
     the exclude-ids sheet (see [sheet-upkeep.md](sheet-upkeep.md)).
   - A cleanup done late in the day isn't showing: the Finalsite file loads on a
     file drop, not a fixed schedule, so it may show the next day.
   - A number doesn't match what was just typed into a sheet: expected. Sheet
     edits don't reach the dashboard until the goals models rebuild. Ask the
     data team to rebuild them.

2. **Adding a new grade or school?** Nothing is hand-entered into the school ×
   grade spine; it builds from PowerSchool and Focus once a student is enrolled
   in that grade. A grade being recruited for with nobody enrolled yet is
   entered in **Finalsite** under the recruitment year. It reaches the dashboard
   only while `finalsite_recruitment_year` is ahead of `current_academic_year`
   (between SRE's rollover and the July 1 bump); while the two are equal it has
   no row, and its goals drop out. Goals for it come through the goals
   reconciliation ([goals-sheet.md](goals-sheet.md)), not hand-typed rows.

## For an engineer: troubleshooting a count discrepancy

Standard checks, roughly in order of likelihood:

1. **Missing crosswalk mapping.** Pull
   `distinct _dagster_partition_key, detailed_status, enrollment_type` from
   `int_finalsite__status_report_unpivot` for the recruitment year and anti-join
   against `stg_google_sheets__finalsite__status_crosswalk` on all three.
   `latest_status_calc` in `int_tableau__finalsite_student_scaffold` inner-joins
   the crosswalk on `_dagster_partition_key`, `enrollment_type` and
   `detailed_status`, so an unmapped pair is dropped silently. Fix it in the
   sheet ([sheet-upkeep.md](sheet-upkeep.md)).
2. **Invalid or QA-flagged rows.** Mapped statuses with
   `valid_detailed_status = false` or `qa_flag = true` are excluded by the same
   join. `valid_detailed_status = false` means the status is not legitimate for
   that `enrollment_type` (New vs Returning): a data-entry mismatch in
   Finalsite.
3. **Same-day status tie.** `latest_status` is the latest `status_start_date`,
   ties broken by `status_order desc`, so two statuses set the same day can pick
   the wrong one. An accepted Finalsite limitation: use the Reset Protocol, not
   a code fix (doc, _Known data model caveats_).
4. **Test records.** Check `stg_google_sheets__finalsite__exclude_ids` for the
   student.
5. **Ingestion lag.** `stg_finalsite__status_report` loads on a file-drop
   sensor, not a cron; a very recent Finalsite edit may not have landed.
6. **Stale goals table.** For a goal-value discrepancy, run the freshness check
   in the entry file's rules before assuming a code bug.
7. **Student missing entirely.** A student Finalsite has no record for never
   reaches Progress to Goals; `is_missing_finalsite_record` on the QC worklist
   lists them ([qc-worklist.md](qc-worklist.md)).

## Scaffold facts that look like bugs

- `stg_powerschool__schools.school_level` is one value per school, from
  `high_grade` (Sumner is forced to `ES`). The scaffold's own per-grade `CASE`
  is what gives Sumner grades 5-6 `MS`. Don't read the SIS field instead.
- The design spec's _Verification_ section showed `schoolid` aligns between
  `stg_powerschool__schools` (at `state_excludefromreporting = 0`) and
  `int_people__location_crosswalk` for every case that matters
  ([spec](../../../../docs/superpowers/specs/2026-07-20-fresh-dashboard-scaffold-source-swap-design.md)).
