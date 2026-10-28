# PowerSchool stored grades extract — design

Refs #5704

> Revised 2026-10-28 after review on #5705. Where the original design below and
> the _Revision 2026-10-28_ section disagree, the revision wins: it replaces the
> sources, adds district wrappers, and changes the MS `Comment` handling.

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

## Revision 2026-10-28

Review on #5705 found that the original sources break the layer rules in
`.claude/rules/dbt-architecture.md`, and asked for district wrappers. This
section replaces _Sources_, _Filters_, the source column of _Output columns_,
_Tests_, _Quarterly runbook_, and _Exposure_ above, and removes district
wrappers from _Out of scope_.

### Why the sources changed

- A1: an `rpt_` may read only marts and domain `int_` models.
  `base_powerschool__final_grades` and `int_powerschool__gradescaleitem_lookup`
  are source-level, and `stg_powerschool__students` is staging.
- A5: an `rpt_` may not dedupe, so the gradescale-name dedupe is gone.
- A2: an `rpt_` reads a mart when one covers the entity. `fct_grades_term`
  covers term grades (and #6084, which dropped late-enrolled students, is fixed
  by #6085), but the mart chain has no PowerSchool `sectionid` or section
  `termid`: `dim_course_sections.identifier` is the section number. The import
  needs both, so the extract reads domain `int_` models until the marts carry
  them. Tracked in #6174; when it lands, move the extract onto the marts.

### kipptaf view sources

| Model                              | Join                                                | Provides                                                                                                                                                                                                                                         |
| ---------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `int_students__final_grades`       | driving model                                       | `student_number`, `schoolid`, `storecode`, `term_grade_points`, `term_percent_grade_adjusted`, `term_letter_grade_adjusted`, `potential_credit_hours`, `_dbt_source_project`; `comment_value` after upstream change 1                            |
| `int_students__course_enrollments` | `inner join` on `cc_dcid` and `_dbt_source_project` | `cc_sectionid`, `cc_course_number`, `courses_course_name`, `courses_credittype`, `teacher_lastfirst`, `school_name`, `school_level`, `sections_termid`, `students_grade_level`, `is_homeroom`; `courses_gradescale_name` after upstream change 2 |

Both models are unique on the join key (`cc_dcid` + `_dbt_source_project` for
course enrollments; `cc_dcid` + `storecode` + `_dbt_source_project` for final
grades), so the join cannot fan out. Focus (Miami) rows in
`int_students__final_grades` carry a null adjusted percent and drop out at the
first filter below.

### Upstream changes (part of the build)

1. `comment_value` on `int_students__final_grades`: the PowerSchool branch
   selects it from `base_powerschool__final_grades`; the Focus branch pads it
   with `cast(null as string)`. The model currently uses
   `full union all corresponding`, which `.claude/rules/dbt-sql.md` bans;
   convert it to an enumerated `union all` while editing it.
2. `courses_gradescale_name` on the course data that feeds
   `int_students__course_enrollments`: in the powerschool package's
   `base_powerschool__sections`, `left join stg_powerschool__gradescaleitem` on
   `id = courses_gradescaleid`. That joins the scale's own row
   (`gradescaleid = -1`); `id` carries an error-level `unique` test, so it is
   one-to-one and needs no dedupe. This is a package column add, so follow
   _kipptaf source consumers of district columns_ in
   `.claude/rules/dbt-models.md` (two PRs, or the single-PR staging pattern).

### Filters (baked in)

- `term_percent_grade_adjusted is not null`
- `not is_homeroom` — replaces `course_number != 'HR'`. `is_homeroom` matches
  `like 'HR%'`, which is broader; the parity check confirms no graded course
  other than `HR` starts with `HR`.
- `potential_credit_hours != 0` — unchanged, with its SQL comment.
- `school_level in ('MS', 'HS')` — ES is excluded on purpose. Stored grades feed
  MS/HS report cards and transcripts, and ES grades are not stored through this
  import. Camden has ES rows that pass the other filters, so this filter is
  load-bearing.

### Output column changes

| Column            | New source / logic                                                                                                    |
| ----------------- | --------------------------------------------------------------------------------------------------------------------- |
| `grade_level`     | `students_grade_level`                                                                                                |
| `credit_type`     | `courses_credittype`                                                                                                  |
| `course_number`   | `cc_course_number`                                                                                                    |
| `course_name`     | `courses_course_name`                                                                                                 |
| `sectionid`       | `cc_sectionid`                                                                                                        |
| `termid`          | `sections_termid`                                                                                                     |
| `gradescale_name` | `courses_gradescale_name`                                                                                             |
| `Comment`         | `comment_value` on HS rows, null on MS rows: `if(school_level = 'HS', comment_value, null)`. See _MS `Comment`_ below |

All other columns keep the logic in _Output columns_ above. The contract YAML
must spell `PotentialCrHrs`, `EarnedCrHrs`, and `Comment` in exactly that case.

### MS `Comment`

MS rows carry a null `Comment` instead of the MS run dropping the column, so MS
and HS use one query. This depends on PowerSchool's stored grades import
accepting a blank comment without rejecting the row or clearing an existing
comment. Confirm with a test import before the first live MS run (see
_Validation additions_). If a blank comment is not safe, the MS runbook goes
back to `select * except (school_level, Comment)`.

### District wrappers

Each NJ project (`kippnewark`, `kippcamden`, `kipppaterson`) gets
`models/extracts/powerschool/rpt_powerschool__stored_grades.sql`, following the
`rpt_powerschool__autocomm_*` wrappers:

- selects every kipptaf column except `code_location`, from
  `source("kipptaf_extracts", "rpt_powerschool__stored_grades")`, filtered
  `where code_location = '{{ project_name }}'`;
- adds the table to that project's `kipptaf_extracts` source in
  `models/extracts/sources.yml`;
- properties file is contract columns only, with no tests or descriptions (those
  stay on the kipptaf view);
- lands in `<region>_extracts.rpt_powerschool__stored_grades`.

### Exposures

No exposure in kipptaf. Each NJ project adds one to
`models/exposures/powerschool.yml`: name `powerschool_stored_grades`, label
`PowerSchool Stored Grades Import`, type `application`, `owner.name: Data Team`,
`depends_on: ref("rpt_powerschool__stored_grades")`, and
`config.meta.dagster.kinds: [powerschool]`.

### Tests

Unchanged from _Tests_ above, on the kipptaf view only. The wrappers carry none.

### Quarterly runbook (kipptaf model description)

```sql
select * except (school_level)
from kippnewark_extracts.rpt_powerschool__stored_grades
where storecode = 'Q1' and school_level = 'MS'
```

Swap the region dataset (`kippnewark_extracts`, `kippcamden_extracts`,
`kipppaterson_extracts`), the storecode, and the school level per run. Download
as CSV and import into that region's PowerSchool server.

### Validation additions

1. Parity (unchanged): compare against the saved query using the wrapper, with
   `Comment` excluded on MS rows, since the saved query has none.
2. Blank-comment test import: before the first live MS run, import a small MS
   file with a blank `Comment` into one region's PowerSchool (a test server if
   one is available). Confirm rows load and existing comments are untouched.
