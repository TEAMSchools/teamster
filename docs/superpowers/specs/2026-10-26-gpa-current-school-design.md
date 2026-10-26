# GPA filed under the student's current school

Short design for PR #5531, which now also resolves #6126. Refs #4938.

## Intent

A student's GPA for a year should appear under one school only: the school they
are enrolled at now, or for a past year, the school they were enrolled at when
the year ended. Today the GPA models split or file a student's GPA by the school
the grades are stored under. Reports then disagree, drop students who
transferred, and keep stale rows in the GPA snapshot.

## Decided

- **Filing rule.** `int_powerschool__gpa_term.schoolid` is the student's current
  school for that year: the school of their `rn_year = 1` stint in the package
  enrollment union (latest `exitdate`). When a student has grades but no stint
  that year, fall back to the school with the most potential GPA credit hours.
  `schoolid` stays a label, not part of the grain.
- **Downstream follows the label.** The cumulative-GPA join in
  `int_powerschool__gpa`, the snapshot, the lookback, and the reporting-term
  join keep joining on `schoolid`, which now means the current school.
- **`fct_grades_gpa`** joins only the student's latest stint that year, so a
  student with two stints at one school does not fan out.
- **Snapshot.** `snapshot_powerschool__gpa_term` keeps its `unique_key` and adds
  `hard_deletes: invalidate`. A row whose key leaves the source (a transfer, or
  a label change) is closed instead of staying current. That clears the 431
  student-years that hold two current rows today, with no manual migration and
  no history loss.
- **Merge gate.** The PR does not merge until the network decides which grades
  count toward a student's Y1 GPA (Asana decision task, owner Anthony Walters).

## Not decided here

Which courses the GPA counts: every KIPP school that year ("Combined"), only the
current school, or separate per school, and whether same-year grades from
outside the network count. Cumulative GPA scope follows the same decision. The
rule lives in one place, the `grade_rollup` CTE of `int_powerschool__gpa_term`,
so the decision changes one CTE. The branch implements "Combined" until then.

## Approaches considered

- **A. Redefine `schoolid` as the current school in the package model. Chosen.**
  Smallest diff. The rule lives beside the course rollup, and every consumer
  that already joins on `schoolid` lands on the right school.
- **B. Resolve the current school in kipptaf.** Keeps enrollment logic out of
  the package, but the package's cumulative join, the snapshot, and the lookback
  would still use the old label, so the rule would live in two places.
- **C. Drop `schoolid` and let each consumer join enrollments.** Cleanest grain,
  but it touches every consumer and invites each to resolve "current school"
  differently.

## Left to the builder

- Read the enrollment union by `ref()` inside the package. Check that it builds
  in all three NJ districts and in the Miami archive rebuild.
- Measure before and after in prod: rows per student-year in `fct_grades_gpa`,
  current snapshot rows per student-year, and lookback coverage for transfer
  students.
- After the first snapshot run with `invalidate`, the lookback can read the
  closed stale rows for up to 28 days at past boundaries. Confirm the lookback
  `max()` picks the right one, or filter it.
- CI reads district data through stale staging copies. Seed what the new build
  needs before pushing.
