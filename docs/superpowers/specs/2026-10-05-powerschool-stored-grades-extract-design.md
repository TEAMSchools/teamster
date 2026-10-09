# PowerSchool stored grades extract — design

Refs #5704

## Goal

Replace a personal saved BigQuery query with a version-controlled,
contract-enforced dbt view that produces the quarterly PowerSchool **stored
grades** import file for each NJ region (Newark, Camden, Paterson — each on its
own PowerSchool server). Stored grades drive MS/HS report cards and transcripts,
so the output must be reviewable and reproducible by anyone on the data team.

## Current state

- One person runs a saved query each quarter, editing the storecode, grade band,
  and `_dbt_source_relation` filter by hand per region, then imports the CSV
  into PowerSchool.
- The query joins two **orphaned** views in `kipptaf_powerschool`:
  `stg_powerschool__gradescaleitem` and `stg_powerschool__sections`. Neither has
  a kipptaf dbt model; both were last modified Aug 2025.
- Paterson is already in the kipptaf `base_powerschool__final_grades` and
  `stg_powerschool__pgfinalgrades` unions on main (`b3df984b2`), so no union
  change is needed. Paterson currently has MS grades only (no HS).
- `base_powerschool__final_grades` already carries the course name, credit type,
  teacher name, school name, school level, termid, and the `pgfinalgrades`
  comment — most of the query's joins are redundant.

## Design

### Model

`src/dbt/kipptaf/models/extracts/powerschool/rpt_powerschool__stored_grades.sql`
— a view (directory default), contract enforced, next to the
`rpt_powerschool__autocomm_*` extracts. Lands in `kipptaf_extracts`.

No district wrapper models: the file is pulled manually by filtering the kipptaf
view, not pushed by a regional project. If the import is ever automated, add
thin wrappers per the `extracts/powerschool/` pattern in
`src/dbt/kipptaf/CLAUDE.md`.

### Sources

| Model                                    | Provides                                                                                                                    |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `base_powerschool__final_grades`         | grades, points, storecode, course, credit type, teacher, school, school level, termid, comment, `_dbt_source_project`       |
| `stg_powerschool__students`              | `student_number`, `grade_level` (joined on `studentid` = `id` + `_dbt_source_project`)                                      |
| `int_powerschool__gradescaleitem_lookup` | `gradescale_name` for `courses_gradescaleid` — dedupe to one name per `gradescaleid` + `_dbt_source_project` before joining |

All joins use `_dbt_source_project` equality, not `_dbt_source_relation`.

### Filters (baked in)

Carried over unchanged from the current query:

- `term_percent_grade_adjusted is not null`
- `course_number != 'HR'`
- `potential_credit_hours != 0` — MS/HS courses carry credit hours above 0, so
  this keeps the population correct for now. Leave a SQL comment noting it is
  the rule to revisit if 0-credit courses ever need storing.

### Output columns

Import column names stay exactly as today so the PowerSchool import mapping does
not change.

| Column            | Source / logic                                      |
| ----------------- | --------------------------------------------------- |
| `student_number`  | students                                            |
| `grade_level`     | students                                            |
| `schoolid`        | final grades                                        |
| `gpa_points`      | `term_grade_points`                                 |
| `percent`         | `least(term_percent_grade_adjusted, 100)`           |
| `grade`           | `term_letter_grade_adjusted`                        |
| `storecode`       | final grades                                        |
| `credit_type`     | `credittype`                                        |
| `course_number`   | final grades                                        |
| `course_name`     | final grades                                        |
| `teacher_name`    | `teacher_lastfirst`                                 |
| `sectionid`       | final grades                                        |
| `PotentialCrHrs`  | constant `0`                                        |
| `EarnedCrHrs`     | constant `0`                                        |
| `gradescale_name` | gradescale lookup                                   |
| `schoolname`      | `school_name`                                       |
| `termid`          | final grades                                        |
| `Comment`         | `comment_value` (HS runs only; MS runs drop it)     |
| `code_location`   | `_dbt_source_project` — filter column, not imported |
| `school_level`    | final grades — filter column, not imported          |

`school_level` replaces the current query's hand-edited
`grade_level between 5 and 8` filter. The parity check below confirms the two
select the same students; if any MS school serves a grade outside 5–8 (or the
reverse), revisit before switching over.

The Miami-only citizenship column is dropped (Miami is on Focus).
`code_location` follows the kipptaf extracts naming convention for region
filters.

### Tests

- `dbt_utils.unique_combination_of_columns`: `code_location`, `student_number`,
  `sectionid`, `storecode`. #5221 reports `pgfinalgrades` duplicates at the
  student-course-term grain; if this test fails on that, fix upstream under
  #5221 rather than deduplicating in the extract.
- `not_null` on `student_number`, `schoolid`, `storecode`, `course_number`,
  `sectionid`, `percent`, `grade`, `termid`.

### Quarterly runbook (model description)

```sql
-- HS (Comment populated)
select * except (code_location, school_level)
from kipptaf_extracts.rpt_powerschool__stored_grades
where code_location = 'kippnewark' and storecode = 'Q1' and school_level = 'HS'

-- MS (Comment omitted)
select * except (code_location, school_level, Comment)
from kipptaf_extracts.rpt_powerschool__stored_grades
where code_location = 'kipppaterson' and storecode = 'Q1' and school_level = 'MS'
```

Run once per region and school level, download as CSV, import to that region's
PowerSchool server.

### Exposure

Add an exposure (type `application`, PowerSchool stored grades import) depending
on `ref("rpt_powerschool__stored_grades")`, so the manual consumer is visible in
lineage.

## Validation

1. **Parity:** for Newark Q1 MS of the current year, the new view (with
   `except`) and the current saved query return identical row counts and values
   (`EXCEPT DISTINCT` both directions returns zero rows). Repeat for Camden.
2. **Paterson spot-check:** Paterson Q1 MS row count matches graded MS rows in
   `kipppaterson_powerschool.base_powerschool__final_grades` after the baked-in
   filters; spot-check a handful of rows against PowerSchool.
3. `dbt build --select rpt_powerschool__stored_grades` passes locally and in dbt
   Cloud CI.

## Out of scope

- Automating the PowerSchool import (district wrappers + push).
- Populating real credit hours in `PotentialCrHrs` / `EarnedCrHrs`.
- Dropping the orphaned `kipptaf_powerschool.stg_powerschool__gradescaleitem` /
  `stg_powerschool__sections` views — separate cleanup follow-up.
