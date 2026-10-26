# IGNITE R2I Extract

## What it is

Mathematica is evaluating the IGNITE R2I program at KIPP NJ high schools. The
data team sends Mathematica de-identified student, course and teacher-course
files. Each student appears under a masked `stu_id`, never a KIPP student
number. The files go out in two phases, and the second must join to the first,
so every student must keep the same `stu_id` across both.

Owner: the data team. Charlie Bini owns the lookup sheet.

## Who is in the study

The population is defined once, in `int_ignite__student_years`. Every other
IGNITE model joins to it. A student is in scope for a school year when both of
these hold:

- They had a grades 9-12 enrollment at a New Jersey school that year.
- That year appears on a `resolved` row of the treatment sections sheet.

To add a study year, resolve that year's treated sections in the sheet. No code
change is needed. The sheet drives this both ways:

- A year whose rows are all still `pending` drops out of every IGNITE file,
  treated and control students alike, until one row is `resolved`.
- A `resolved` row with the wrong `academic_year` adds that whole year of NJ
  high school students.

## Where the inputs live

| Input                        | Location                                                                                                                                                | Model                                           |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Treated sections             | `treatment_sections` tab of the [IGNITE R2I Extract Lookups](https://docs.google.com/spreadsheets/d/1FKVaJD-7RIvMkzM1_4mJ8IbNQDlWAXbhpPRw29CkGf8) sheet | `stg_google_sheets__ignite__treatment_sections` |
| NCES school and district IDs | `NCES LEA ID` and `NCES School ID` columns on the Locations tab of the people locations sheet                                                           | `stg_google_sheets__people__locations`          |
| Salt for the masked id       | BigQuery table `kipptaf_restricted.ignite_id_salt`                                                                                                      | source `ignite.ignite_id_salt`                  |

## The salt

The masked `stu_id` is a salted hash of the student number. Federal rules (34
CFR §99.31(b)(2)) say we must not disclose how a de-identified record code is
generated. The salt is what keeps the code from being recomputed.

- **Where it lives.** It is the single row of
  `kipptaf_restricted.ignite_id_salt`. The dataset grants read access to the
  Dagster agent, `dbt-user` and `codespaces` service accounts. A local dev build
  of `int_ignite__student_id_crosswalk` fails with Access Denied for anyone
  without read access.
- **Never change it** while the study runs. A new salt gives every student a new
  `stu_id`, and Mathematica can no longer join phase 2 to phase 1.
- **Never print, log or commit it.** Don't put it in SQL, YAML, dbt vars,
  comments, issues, PRs or Slack. Models read it through `source()`, so the
  compiled SQL never contains it.
- **Why the crosswalk is a table.** `int_ignite__student_id_crosswalk` is
  materialized as a table. The outbound views read the stored ids and never need
  access to the salt.
- **Checks.** The crosswalk's tests fail the build if the salt table is empty
  (no ids), holds more than one row (duplicate students) or holds a null (null
  ids).

Keep a copy of the value in the data team's 1Password vault. If the table is
ever lost, restore that same value. Do not generate a new one.
