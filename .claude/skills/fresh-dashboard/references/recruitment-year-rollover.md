# Update the Finalsite recruitment year

Trigger phrases: "SRE's cycle has rolled over, update FRESH for the new year",
"bump the Finalsite recruitment year", "the goals sheet is now on [year], update
the dashboard". The doc's _Rolling the dashboard over to a new cycle_ has the
owner-by-step table; this is the procedure.

## When

After 15 March, and only when SRE says its cycle has advanced. There is no fixed
date and no revert step: each bump moves one year forward. Don't infer the year
from a calendar date or from ingested data. Finalsite can carry two academic
years of live records at once, which is why `finalsite_recruitment_year` is a
hand-bumped var and not computed (two attempts to compute it were reverted;
`git log` on `int_tableau__finalsite_student_scaffold.sql`).

## Before the bump, in order

Flipping the var before the sheets carry the new year does not error; it returns
zero rows.

**Step 0a: ask for the new SRE workbook.** Ask the user: "Do you have a new SRE
target sheet URL for this cycle?" Read it with the Sheets API
([sre-workbook.md](sre-workbook.md)) and use its cover sheet as the
expected-school list for verification. If it isn't available yet, the rollover
can proceed (the scaffold derives itself), but say the sanity check is deferred.
Don't write the new id into this skill.

**Step 0b: confirm SRE and the data team agree which Finalsite year is active.**
This is the real gate on the rollover.

**Step 0c: new schools or grades.** SRE enters them in Finalsite under the new
year. They reach the scaffold through `finalsite_new`, which returns rows only
while `finalsite_recruitment_year != current_academic_year`: from this bump
until the July 1 `current_academic_year` bump. After July 1 a grade with nobody
enrolled in the SIS has no row again until a student enrolls. Confirm SRE has
entered them before proceeding.

**Step 0d: `status_crosswalk` partition key and columns.**

```sql
select distinct _dagster_partition_key, file_year, count(*) as row_count
from `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__finalsite__status_crosswalk
group by 1, 2
```

Column A (`_dagster_partition_key`) is replaced, not appended: the sheet holds
one year, guarded by
`test_stg_google_sheets__finalsite__status_crosswalk_single_year`.
`latest_status_calc` inner-joins the crosswalk to the status report on
`_dagster_partition_key`, and the `Current` roster branch joins on
`file_year = enrollment_academic_year`, so a stale key empties the dashboard
with no error. Then ask SRE to re-confirm columns D, H and I-P
([sheet-upkeep.md](sheet-upkeep.md) has the questions to ask).

**Step 0e: goals.** Run the reconciliation in [goals-sheet.md](goals-sheet.md)
until it comes back clean, and run its gap-row check.

**Step 0f: exclude_ids.** Ask whether SRE created test records for the new
cycle; add their ids ([sheet-upkeep.md](sheet-upkeep.md)).

**Step 0g: re-confirm the four first-day-of-school dates with SRE.** They are
not derived from either SIS and nothing detects a change. Ask for the new
cycle's first day per region and compare against the `CASE` in
`custom_fdos_dates` (`int_tableau__finalsite_student_scaffold`); AY2026 held
Newark and Paterson August 28, Camden August 24, Miami August 14. The var
supplies only the year, so a start date that moved lands silently wrong. They do
move: Paterson's first day was around September 3 in AY2024 and August 26-28 in
AY2025. Edit the `CASE` and nothing else ([qc-worklist.md](qc-worklist.md)).

## The bump

One line: `finalsite_recruitment_year` in `src/dbt/kipptaf/dbt_project.yml` (for
example `2026` → `2027`). Every site reads the var:

- `int_tableau__fresh_enrollment_scaffold`: `school_directory`'s
  `enrollment_academic_year`, and `finalsite_new`'s filter and gate.
- `int_tableau__finalsite_student_scaffold`: `latest_status_calc`,
  `focus_enrollments_with_finalsite`, `enrollment_lookup`, and the year in
  `custom_fdos_dates`.
- `rpt_tableau__fresh_dashboard_progress_to_goals`: the `School` and
  `School/Grade Level` goal CTEs.
- `rpt_tableau__fresh_dashboard_qc`: `sis_enrollments`.
- `test_int_finalsite__status_order_matches_crosswalk_ranking`:
  `crosswalk_ranking`.

Confirm none reverted to a literal:

```bash
grep -rn 'var("finalsite_recruitment_year")' src/dbt/kipptaf
```

The ad hoc queries in this skill cannot read the var; substitute the year.

## Build and verify

```bash
uv run dbt build \
  --select int_tableau__fresh_enrollment_scaffold+ int_tableau__finalsite_student_scaffold+ \
    test_int_finalsite__status_order_matches_crosswalk_ranking \
  --project-dir src/dbt/kipptaf \
  --target dev \
  --defer \
  --favor-state \
  --state target/prod
```

`--favor-state` is required: without it `--defer` resolves unselected upstreams
to your `zz_<user>_*` schema and fails on anything you haven't built. If it
still fails on a recently added upstream, refresh the prod manifest:

```bash
uv run dbt parse --target prod --project-dir src/dbt/kipptaf --target-path target/prod
```

The selection must include `rpt_tableau__fresh_dashboard_qc`, the SRE-facing
worklist: a bump that empties or inflates it is worth catching. Compare the
scaffold's school list against SRE's cover sheet (step 0a).

After the bump, while the recruitment year is ahead of an SIS's year, that SIS's
comparison columns (`enroll_status`, `sis_entry_date`, the `is_enrolled_*`
flags) are NULL and the comparison flags fall silent; `is_missing_sis_record`
carries the volume. Expected, no action (doc, _Known data model caveats_).

## Parked for the AY2027-2028 rollover

Rename the `focus_student_id` alias in the `finalsite_contact_ids` CTE of both
`int_tableau__finalsite_student_scaffold` and `rpt_tableau__fresh_dashboard_qc`
(#5168). It holds `cast(focus_student_id_prefixed as int)`, the student number,
and shadows the unprefixed `focus_student_id` on
`int_finalsite__contact_id_attributes`. `stg_people__student_logins` names the
same value `student_number`. Rename both models in one change.
