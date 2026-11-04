# The QC worklist and the first-day-of-school dates

What to know before editing `int_tableau__finalsite_student_scaffold` or
`rpt_tableau__fresh_dashboard_qc`. The flag definitions, the expected-status
mapping and the triage order are in the doc: _How Finalsite's `latest_status`
becomes an expected enrollment status_ through _Implementation notes_. Read
those; this file holds the traps.

## First-day-of-school dates

- `is_enrolled_fdos` is computed in the student scaffold as
  `sis_entry_date <= custom_fdos_date`, with the month and day hardcoded per
  region in the `custom_fdos_dates` `CASE` and the year from
  `var("finalsite_recruitment_year")`. It does not pass through either SIS's own
  `is_enrolled_fdos`: Focus uses one network-wide first day, which marked most
  Miami students late, and PowerSchool's is per school. Don't repoint it at the
  upstream flag, and don't change `int_extracts__student_enrollments` or
  `int_focus__student_enrollment_roster`; their own flags serve other consumers.
- When SRE changes a first day, edit the `CASE` and nothing else. The dates are
  a rollover step ([recruitment-year-rollover.md](recruitment-year-rollover.md),
  step 0g): the var carries the year forward and leaves the month and day, so a
  moved date is judged against last year's with no error and no failing test.
- It is a bare comparison on purpose, so a student with no SIS record reads
  NULL. Wrapping it in `if(<cmp>, true, false)` to match its siblings would turn
  those NULLs into `false`; that is a regression, not a cleanup.
- A dev-vs-prod comparison before school starts shows no movement: at rollover
  both SISs give every student the same bulk entry date, ahead of any first day,
  so every student with a record reads `true` in both versions. A zero delta
  then is expected, not evidence the change is inert.

## Flags

- Five flags. A same-day status tie is not one of them and should not become
  one: the pending statuses in `is_enroll_status_mismatch` cover what SRE acts
  on, and the tie itself is fixed with the Reset Protocol.
- `is_grade_level_mismatch` and `is_school_mismatch` are wrapped in
  `if(<cmp>, true, false)`, so they read `false`, not NULL, when the SIS side is
  missing. Don't use `is null` on them as a missing-SIS proxy.
- `is_missing_finalsite_record` is the only flag sourced from the SIS side. It
  starts from `int_extracts__student_enrollments` (`enroll_status = 0`,
  recruitment year) and is `union all`ed onto the worklist, since a student
  Finalsite never knew cannot be in a Finalsite-sourced roster. Miami's
  Finalsite id comes from `int_finalsite__contact_id_attributes`, because Miami
  rows there carry no `infosnap_id`. Don't add a `finalsite_recruitment_year`
  filter to its anti-join against `stg_finalsite__status_report`: that was
  measured and rejected, because it also flags students whose record sits in an
  adjacent cycle. Use this flag to answer "PowerSchool says N, the dashboard
  says fewer" instead of tracing students by hand.
- `is_enroll_status_mismatch` has two directions, matching the SQL's two
  branches: expected `0` against SIS `2`/`3`, and expected `2` against SIS `0`.
  The second covers both the "left" and the "pending" statuses; `latest_status`
  tells them apart. Don't split it into more directions.
- `finalsite_expected_enroll_status` takes only `0` and `2`, deliberately the
  SIS's own `enroll_status` codes so the compared columns mean the same thing.
  Don't renumber them or split `2` per situation. The pending list (`Accepted`,
  `Assigned School`, `Did Not Enroll`, `Campus Transfer Requested`,
  `Parent Declined`, `Enrollment In Progress`) is SRE-owned; `Did Not Enroll`
  and `Parent Declined` read as exits, and a bare `Accepted` may match no rows.
  Confirm with SRE before changing it.
- Retention (grade repetition) makes `is_grade_level_mismatch` and
  `is_school_mismatch` fire on correctly recorded students. That question is
  with SRE (doc, _Open questions_); don't build suppression or labeling logic
  unless they come back asking.
