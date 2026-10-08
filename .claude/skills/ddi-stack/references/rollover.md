# Yearly rollover

The reference doc's "Yearly upkeep" lists the cycle; this file carries the
operational detail. Family SQL carries no hardcoded years — every current-year
filter rides the repo-wide `current_academic_year` var (July rollover), so the
family needs no code change at rollover beyond the items below.

1. **AppSheet re-tag** (ADs; QC Marya Shukla). Nothing shows anywhere until the
   year's assessments are tagged. Spot-check by querying
   `kipptaf_google_appsheet.stg_google_appsheet__illuminate_assessments_extension`
   for the new year's assessment ids (`module_type`, `administered_at`, the
   three `regions_*` fields populated).
2. **Goals sheet.** New-year rows in the academic-goals named range of the
   Assessments spreadsheet. The staging and intermediate uniqueness tests warn
   on duplicate keys — check them after the paste.
3. **Standard domains.** Update the standard-domains named range (Marya Shukla)
   when standards or domains change for the year; largely static otherwise.
4. **Reporting terms.** Confirm the year's RT rows exist (shared hub; the feeds'
   `term_administered` and the dashboards' terms break visibly when they lag).
5. **Refresh schedule** (August). Review the `ddi_suite` exposure's
   `cron_schedule` list in `src/dbt/kipptaf/models/exposures/tableau.yml` with
   the assessment director — those crons are real Dagster schedules.
6. **Workbook default year.** Bump the DDI Suite tabs' default year filter (a
   Tableau workbook edit, requested every fall).
7. **Course-crosswalk audit** (fall, once master schedules settle — a July run
   sees thin enrollments). Compile the dbt analysis
   `src/dbt/kipptaf/analyses/ddi_course_subject_crosswalk_audit.sql`
   (`uv run dbt compile --select ddi_course_subject_crosswalk_audit --target prod --project-dir <checkout>/src/dbt/kipptaf`
   — compile is read-only, and `--target prod` resolves the refs to prod
   relations and picks up the current-year var) and run the compiled SQL
   read-only; hand the result to c3/academic ops to confirm which courses are
   tested subjects (connected to Illuminate results, state testing, both, or
   eventually Focus Apex assessments), then add the confirmed rows to the course
   subject crosswalk named range. Expect homeroom, lunch, and co-curricular rows
   in the output — those stay off the sheet.
8. **The WPP TODO.** `rpt_tableau__ddi_dashboard` carries `module_type != 'WPP'`
   with a `TODO: Remove SY26` marker; check with the owner whether this is the
   year it goes.
