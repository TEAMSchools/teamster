# Move source-data warn tests to their point of entry

Refs [#6146](https://github.com/TEAMSchools/teamster/issues/6146). Parent:
[#5558](https://github.com/TEAMSchools/teamster/issues/5558).

## Intent

#5558 turns warn tests into tickets that land with the people who can fix the
source record. A ticket can only name the record, the period, and the school if
the test runs on the earliest model that sees the bad data. Several warn tests
today sit downstream, on values our own code derives. This change moves each one
to its point of entry, so it can become a ticketed test.

## Goals

- Each test below runs on the earliest model that holds the bad source rows and
  returns enough columns to route a ticket (see _Ticket columns_).
- The old downstream copy is deleted in the same PR, so no check goes missing
  between merges.
- Every moved test is `warn` and becomes a Dagster check.

## Non-goals

- Fixing the source data. Ops, Academics, and Enrollment own that.
- Routing tickets. That is #5558.
- Item 6 (final grades outside a stint). It is held until someone checks whether
  Focus report cards show those grades. Its test stays where it is.

## Anti-goals

- A test that silently never becomes a Dagster check (missing `meta.dagster.ref`
  or `package:`).
- A package test that fails the build because it defaulted to `error`.
- A model change made only to host a test.
- Removing logic that a test was mistaken for. Item 13 shows the risk.

## Constraints

- Package tests set `config: severity: warn` explicitly. Source packages default
  to `error`.
- Singular package tests set `meta.dagster.ref` with `package: <source>` in the
  package's `tests/properties.yml` (`.claude/rules/dbt-yaml.md`).
- Moving a test changes its Dagster check key, so its check history starts over.
  That is accepted.
- Test descriptions name the source system, what is wrong, and what to change
  there (_Tests on marts and `rpt_` models_, source-data bullet).
- No row values in the spec, commits, or PR. Counts only.

## Approaches

1. **One PR, one commit per dbt project (chosen).** Commits go in the order
   powerschool, focus, finalsite, kipptaf. The kipptaf commit deletes the old
   copies, so the PR as a whole never drops coverage.
2. **One commit per item.** Rejected. Several items edit the same
   `tests/properties.yml`, so their changes would be spread across commits and
   reviewers would have to read the same file repeatedly.
3. **New `int_` models to host tests** (items 9, 11). Rejected. A model added
   only for a test duplicates an existing grain (A4). Singular tests do the job.

The user chose one PR for all 13 items, and approach 1.

## Ticket columns

Most tests return the record, the period, and the school. Some records belong to
the network, not a school: an Illuminate assessment, a repository field, an
AppSheet tag. Tests on those return the record's id, its title, and its academic
year, plus `creator_*` from `int_illuminate__assessments` where the model has
it, and no school (my call). Item 9 works per sitting, so it also returns
`student_assessment_id`. It does not join enrollment to find a school. A single
assessment's bad academic year accounts for every one of its sittings, so the
owner to route to is the assessment's creator, not a school.

## Decisions per item

Counts are from 2026-10-26, from hand-written equivalents of each test. Stored
failures in `*_dbt_test__audit` were stale for several tests. Paths are under
`src/dbt/`.

### powerschool package

**Item 1 NJ: cohort ahead of entry → skipped grade in enrollment history.**
Delete
`powerschool/tests/base_powerschool__student_enrollments__cohort_not_ahead_of_entry.sql`
and its `tests/properties.yml` entry. Add a singular test on
`int_powerschool__ps_enrollment_all`. Logic: take 1 row per student and academic
year (the highest grade, excluding `schoolid = 999999`). Flag a row when the
prior row is the immediately preceding academic year, the grade rose by more
than 1, and the current grade is 9 to 12. Scope: **all history** (user
decision). Expected: 117 rows across Newark and Camden (Paterson 0); 7 in the
current year. Return student, academic year, both grades, and school. Summer
credit recovery can still false-positive. Say so in the description. The model
has no `academic_year`, only `yearid` from a term join, which is null when
`entrydate` falls outside every term. Derive the year from `entrydate`.

**Item 11: two Bucket programs in one subject.** New singular test on
`int_powerschool__spenrollments`. It flags 2 different
`specprog_name like 'Bucket%'` stints for one student, the same subject (the
text after the hyphen), and the same academic year whose date ranges overlap.
Sequential stints are legitimate: rollout-PD amendments exit one bucket and
enter another, and `int_students__bucket_assignments` resolves those by latest
assignment date (its description). The #5693 duplicates are concurrent, and
every pair shares an `enter_date`. Expected: 54 pairs, all in AY2025. The model
has no `schoolid`, so the test joins whatever upstream supplies it. The
description states the #5693 rule for concurrent duplicates: the lower-numbered
bucket wins, and Ops deletes the other record in PowerSchool. Do not add a
tiebreaker to `int_extracts__student_enrollments_subjects`.

Keep the `n_active_assignments <= 1` warn test on
`int_students__bucket_assignments` (my call). It also covers Miami's Focus
groups, which this test does not, so deleting it would drop Miami coverage.

**Item 12: shared entry date.** No new test. The
`dbt_utils.unique_combination_of_columns` on `(studentid, entrydate)` in
`int_powerschool__ps_enrollment_all.yml` already covers it and fails 2 groups
(Newark 1, Camden 1). Give it a `name:` and a description naming the source fix.
Keep its `where: schoolid != 999999 and entrydate < exitdate`: without it,
no-show stints add about 57 false groups in Newark. It is a generic test on its
own model, so it needs no `meta.dagster.ref`. In kipptaf, replace the
`TODO(#4835)` block in `fct_student_attendance_streaks.sql` (line 14) with a
1-line comment naming that test. The dedupe stays.

### focus package

**Item 1 Miami.** Delete
`kipptaf/tests/int_extracts__student_enrollments__miami_cohort_not_ahead_of_entry.sql`
and its entry. Add the same skipped-grade test as NJ, as a singular test in
`focus/tests/` on `int_focus__student_enrollment_roster`. Do not use
`int_focus__student_enrollment`, which has no grade. The count is unmeasured;
the builder records it. History covers only the Focus years. The frozen
PowerSchool archive is out of scope.

**Item 2a: course period with no lead teacher.** Add `not_null` on `teacher_id`
in `focus/models/staging/properties/stg_focus__course_periods.yml`, with
`severity: warn` and a description. The staging model has no year filter, so the
test returns 97 rows across all years against 91 in AY2026. That is accepted,
because #5558 wants all history.

**Item 3 Miami: contact with no name.** Add `not_null` with `severity: warn` on
`contact_first_name` and `contact_last_name` in
`focus/models/intermediate/properties/int_focus__student_contacts.yml`.
Expected: 2 rows.

**Item 4: Miami school with a calendar but no students.** Delete
`kipptaf/tests/int_students__calendar_day__zero_enrollment_in_session_days.sql`
and its entry. Add a singular test in `focus/tests/`: `int_focus__calendar_day`
left-joined to `int_focus__student_enrollment_roster` on school and academic
year, keeping calendars with no enrollment. Group it by school and year,
returning the day count. The Miami and year filters go away. The builder
confirms both models key the school the same way. Expected: 2 schools.

### finalsite package

**Item 3 NJ.** Add `not_null` with `severity: warn` on `contact_first_name` and
`contact_last_name` in
`finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml`.
Expected: 10 last-name rows (Newark 4, Camden 6). The package model also builds
in kippmiami, where Finalsite contacts exist but kipptaf does not union them.
The builder counts kippmiami failures; if they are noise, scope the test with
`where`.

Delete both `not_null` tests on `int_students__contacts` (kipptaf), and update
the comment above them.

**Item 8: one Focus student, more than one Finalsite contact.** Move the
`unique_combination_of_columns` from the kipptaf union
`int_finalsite__contact_id_attributes.yml` to the package model of the same
name. Use `unique` on `focus_student_id_prefixed` with
`where: focus_student_id_prefixed is not null` and `severity: warn`. The package
holds 1 region, so `_dbt_source_project` drops out of the key. Expected: 6 keys,
all kippmiami. Rewrite the kipptaf column description that says the model-level
test keeps `rpt_tableau__fresh_dashboard_qc` honest, so it points to the package
test.

### kipptaf

**Item 2b: lead teacher with no staff-roster match.** Rewrite
`kipptaf/tests/test_focus_course_sections_teacher_resolves.sql` to flag only
rows where Focus has a lead teacher (`teacher_id is not null`) that does not
resolve to the roster. Join the kipptaf wrapper `int_focus__course_periods`
(which carries `teacher_id`, `period_id`, and `school_id`) to return the school,
the period, and the course period. Keep the `meta.dagster.ref` on
`int_students__course_sections`. Update the mention in
`int_students__course_sections.yml` (around line 45). Expected: 37 rows.

**Item 5: duplicate academic goals test.** Delete the
`unique_combination_of_columns` in `int_assessments__academic_goals.yml`. The
staging test on the same 5 columns stays, and so does the staging description
sentence saying the int model does not dedupe.

**Item 7: replacement assessment with no region tag. The test stays on the
scaffold (my call).** The failure is not an empty tag. The 1 failing row's
canonical assessment is tagged, but not for the student's region. No internal
member has an empty `regions_assessed_array` today, and Apex is coalesced to
Miami. "Replacement" is decided per student, and the student's region comes from
their school, so `int_assessments__scaffold` is the earliest model that can
tell. An empty-tag test upstream would return 0 rows and miss this case.

- Keep `int_assessments__scaffold__replacement_region_untagged` where it is.
- Add `meta.dagster.ref` to `int_assessments__scaffold`; it has none today.
- Rewrite its description. The source fix is either adding the student's region
  to `regions_assessed` in the AppSheet Illuminate assessments extension, or
  removing the student from the assessment in Illuminate.

**Item 9: assessment taken before its academic year.** Delete the model-level
`expression_is_true` in `int_assessments__scaffold.yml`. Add a singular test in
`kipptaf/tests/` that joins
`stg_illuminate__dna_assessments__students_assessments` to
`int_illuminate__assessments`. It flags
`date_taken < date(academic_year_clean, 7, 1)` with no year filter, and skips
`academic_year_clean < 2000`, where the 0 and 1 values make `date()` fail. Set
`meta.dagster.ref` to the staging model. No model joins the two today before the
scaffold (the user confirmed this approach). Expected: 18,391 sittings across
429 assessments; 2,237 in the current year. The cleanup is #3801.

**Item 10: repeated word fields in Sight Words quizzes.** Add a singular test
that groups `stg_illuminate__dna_repositories__repository_fields` by repository
and label, keeps repositories in the `Sight Words Quiz` scope (through
`int_illuminate__repositories`), and flags counts over 1. Other scopes repeat
labels legitimately: 1 `Reporting` repository, plus 8 repositories with no
`int_illuminate__repositories` row. Set `meta.dagster.ref` to the fields staging
model. Expected: 6 repositories. Delete the dashboard test and its `TODO(#5700)`
in `rpt_tableau__sight_words_dashboard.yml`, and update the repeat-row sentence
in that model's description.

Check this before deleting: the dashboard's uniqueness test is also its only
grain test. Its `rpt_` model must keep a grain test at `error`
(`.claude/rules/dbt-yaml.md`). If the dashboard's grain is clean once Illuminate
is fixed, the builder still can't flip it to `error` while the source defect
remains. Keep it at `warn` with a `TODO(#6146)` pointing at the new source test,
instead of deleting it. The builder settles this with a prod count.

**Item 13: `tiebroken_attrs` stays.** The issue assumed it hides Illuminate
academic-year mismatches. The data says otherwise. 2,423 student and
canonical-assessment groups have rows at more than 1 school. In 2,385 of them
(98%), the student was rostered to a section at a second school but took the
assessment at only 1. Groups with and without a year-mismatched member show the
same split, and no group mixes Illuminate academic years. `tiebroken_attrs`
sorts sittings first, so it credits the result to the school of the sitting.
That is a business rule. Removing it would duplicate rows in
`int_assessments__response_rollup` and its 15 children.

So:

- Rewrite the comment above `tiebroken_attrs` (lines 108–115) to say what it
  settles: a student rostered at more than 1 school for one canonical
  assessment.
- Rewrite the `any_value` comment (lines 166–168) and drop its `#3801`.
- Keep the `#3801` reference at line 70, which is about `date_taken` drift and
  is accurate.
- In `rpt_gsheets__kippfwd_miami_roster.sql` (line 116), drop `#4795` from the
  `pending` comment, because #4795 is closed. Keep `#4796`.
- Update the comment on `int_illuminate__assessments.yml` (lines 9–13), which
  says the mismatch causes "cross-school groups in response_rollup".

Both SQL comment edits mark their models `state:modified`, so CI rebuilds the
rollup's 15 children. That is accepted; the comments are wrong today.

## Verification

- `uv run dbt parse --no-partial-parse` on main and on the branch, in kipptaf,
  powerschool, focus, and finalsite. Diff the test node names. The diff must
  show exactly the adds, removes, and renames above.
- Build each new or changed test in dev against prod data (`dbt-local-dev`
  skill) and compare its count with the expected count. A different count gets
  explained before merge.
- Build `int_assessments__response_rollup` and confirm its SQL changes are
  comment-only (strip comments and compare).
- Check with `rg` that no reference to a deleted test name remains, in
  `--include='*.{sql,yml,md}'`.
- `trunk check --force --no-fix` on every changed file.

## Left to the builder

- The join that supplies the school for item 11.
- The school-key match between Focus calendar and roster for item 4.
- Exact test names, following each folder's existing pattern.
- Whether item 3's Finalsite test needs a `where` for kippmiami.
- Item 10's dashboard grain test: delete it or keep it at warn, per the count.
- Updating #6146 once the PR is open: items 7, 9, 11, 12, and 13 differ from the
  issue text.
