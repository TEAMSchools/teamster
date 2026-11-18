# STAT Dashboard Data Model

## What it is

The State Testing Analysis Tool (STAT) is the Tableau workbook KTAF uses to read
state assessment results across Newark, Camden, Paterson and Miami. School
leaders, regional teams and the data team use it to answer two different
questions that are easy to confuse:

- How did our students do? Student-level scores, proficiency, year-over-year
  change, and teacher rosters.
- How did we do against everyone else? KTAF proficiency next to the host city,
  the state and, in Miami, a named set of neighborhood schools.

The second question has no warehouse source. Nobody publishes comparison
proficiency in a form the warehouse can ingest, so it is typed into a Google
Sheet by hand. Most of the surprises in this pipeline come from that.

Owner: Gaby Rangel. Inheriting: Anthony Walters, Director, Data.

The workbook is exposure `state_testing_analysis_tool` in
`src/dbt/kipptaf/models/exposures/tableau.yml`, identified by its Tableau LSID
in `config.meta.dagster.asset.metadata.id`. It depends on two models,
`rpt_tableau__state_assessments_dashboard` and
`rpt_tableau__state_assessments_dashboard_comps`. The exposure sets no
`cron_schedule`, so Dagster does not refresh the extracts; Tableau Server does.

## How it fits together

```text
Pearson NJ history (frozen)       Cambium NJ (Spring 2026 on)
district pearson package          district cambium package
int_pearson__all_assessments      int_cambium__all_assessments
          |                                 |
kipptaf int_pearson__all_         kipptaf int_cambium__all_
assessments (passthrough)         assessments (passthrough)
          \                                /
           +--> kipptaf int_assessments__state_nj_scores <-- crosswalk sheet
                              |
FL: int_fldoe__all_assessments|
          \                   v
           +--> int_assessments__state_scores
                    |                      |
                    v                      v
Pearson student --> rpt_tableau__state_    int_tableau__state_assessments_
list report         assessments_dashboard  demographic_comps
(preliminary)          ^    |                          |
                       |    |                          v
          comps sheet -+----|-----> rpt_tableau__state_assessments_dashboard_comps
     (state_comps CTE)      |                          |
                            v                          v
            Landing Page, Overview, Demographics,   Advanced Comps
            Teacher/Student Roster, Proficiency
            YoY, Sarba's Report (hidden)
```

The preliminary list report also feeds the demographic comps model, and the
comps sheet also feeds it test-code metadata. Enrollments, goals, schedules and
i-Ready join onto the score view; enrollments onto the demographic comps.

Every model in the reporting chain is a view: both `rpt_` models,
`int_tableau__state_assessments_demographic_comps` and the kipptaf
`int_pearson__all_assessments` and `int_cambium__all_assessments` passthroughs.
Under them are tables: `int_assessments__state_nj_scores`,
`int_assessments__state_scores`, the district pearson and cambium models,
`int_extracts__student_enrollments` and the two sheet staging models. A new
score reaches the workbook only after those tables rebuild and the Tableau
extract refreshes.

## Terms

- `academic_year`: the starting year of the school year. A spring 2026 test is
  `academic_year = 2025`. Published labels ("2026 results") run one ahead.
- Comps: comparison proficiency figures, the percent of students proficient in
  the host city, the state or the Miami neighborhood set, for a test, year,
  region and demographic subgroup.
- Comparison entity (`comparison_entity`): who a comps row describes. From the
  sheet: `City` (the host city's district), `State`, and `Neighborhood Schools`
  (Miami only). Derived from KTAF's own scores: `Region` (KTAF in that region),
  `KTAF NJ` and `KTAF FL`.
- Region partner: for a comps row, the `Region` row with the same year, school
  level, grade band, assessment, discipline, test code, region, demographic
  group and subgroup. The booleans `region_matched`, `region_outperformed` and
  `region_matched_or_outperformed` compare a row with its partner.
- Comps sheet: the Google Sheet of hand-entered comps, read through
  `stg_google_sheets__state_test_comparison_demographics`.
- Crosswalk sheet: the Google Sheet mapping a test's vendor UUID to the correct
  network student number, read through
  `stg_google_sheets__pearson__student_crosswalk`. Named for Pearson, it serves
  every NJ vendor.
- Absent, present-but-wrong, unmatchable: the three ways a score fails to reach
  a student. Absent: the vendor's local student id is null. Present-but-wrong:
  it is filled but is not the student's network number. Unmatchable: the student
  has no enrollment in the test's own year and district, so no crosswalk row can
  help. Classify by mode, never by vendor; either vendor can produce any mode.
- Tiers: the evidence levels in
  `src/dbt/kipptaf/analyses/state_assessment_tiered_crosswalk_match.sql`, which
  proposes crosswalk rows. A: state id, both names and date of birth. B: the
  same with no usable date of birth. C: date of birth and both names while the
  state id disagrees. D: date of birth and last name only, never auto-resolved.
  Every tier also needs an enrollment in the test's year and district, and
  grade-coded tests (`03`-`08`) need a matching grade.
- Interim or media comps: comps typed in from press coverage or district decks
  before the official files arrive. A percentage, no count, and only `Total` /
  `All Students`.
- `remove_row`: comps sheet flag. `TRUE` marks the high-school-only ALG01 rows
  that the staging model removes from the main rows and re-aggregates into one
  weighted total. `FALSE` everywhere else.
- `aligned_test_code`: the network test code, the same across vendors and states
  (`ELA03`, `MATGP`, `SCI11`, ...). It is `test_code` in both `rpt_` models.
- `assessment_version`: which form produced an NJ row: `PARCC`, `NJSLA`,
  `NJSLA Science`, `NJGPA` (Pearson) or `NJGPA-A` (Cambium's adaptive form, on a
  different score scale). Cambium NJSLA rows carry `NJSLA` or `NJSLA Science`;
  only NJGPA has a separate Cambium version. `assessment_name` stays `NJGPA` for
  both, and the comps join keys on `assessment_name`.
- Preliminary scores: early spring results from Pearson's student list report,
  `results_type = 'Preliminary'`. Official rows are `'Actual'`.
- Proficient (`is_proficient`), set upstream per test: NJSLA and PARCC level 4
  or higher; NJSLA Science level 3 or higher; NJGPA level 2 (Graduation Ready);
  Florida FAST, FSA, Science and EOC level 3 or higher.

## Where the data comes from

- Pearson NJ score files, PARCC through December 2025. History only. District
  pearson-package `int_pearson__all_assessments` (Newark, Camden, Paterson),
  read by the kipptaf passthrough of the same name through `source()`, then
  `int_assessments__state_nj_scores` and `int_assessments__state_scores`.
- Cambium TIDE NJ files, Spring 2026 on. District cambium staging, mapped and
  filtered in each district's cambium-package `int_cambium__all_assessments`,
  read by the kipptaf passthrough of the same name, then
  `int_assessments__state_nj_scores` and `int_assessments__state_scores`.
- Pearson student list report (preliminary). District
  `int_pearson__student_list_report`, unioned by the kipptaf model of the same
  name, read directly by both reporting models.
- FLDOE files for Miami. `int_fldoe__all_assessments`, then
  `int_assessments__state_scores`.
- PowerSchool and Focus, owned by regional operations: enrollments
  (`int_extracts__student_enrollments`), subjects and tutoring
  (`int_extracts__student_enrollments_subjects`) and courses
  (`base_powerschool__course_enrollments`).
- Goals: `int_assessments__academic_goals`.
- The comps sheet and the crosswalk sheet, both kept by the data team.

The NJ vendor changed on a date, not per assessment: through December 2025 it is
Pearson; Spring 2026 and after is Cambium, for NJSLA, NJSLA Science, NJGPA and
the Algebra I, Algebra II and Geometry end-of-course tests. The Pearson
relations will not gain rows, so a gap in one cannot be fixed by a re-pull.
Paterson has no NJGPA file (`stg_pearson__njgpa` and `stg_cambium__njgpa` are
disabled there) and no end-of-course file yet, and its Pearson NJSLA history
came through its own ID-remapping `int_pearson__njsla` and
`int_pearson__njsla_science`, now frozen with the rest of the Pearson models.
The Cambium side is in
[`src/dbt/cambium/CLAUDE.md`](https://github.com/TEAMSchools/teamster/blob/main/src/dbt/cambium/CLAUDE.md).

## Dashboard outline

Six published views and one hidden dashboard, on two embedded extracts. What
each view draws and filters lives in the workbook; the descriptions below come
from the model columns. Any question about a calculated field needs the `.twb`
(see the `tableau-workbook-xml` skill); the Tableau MCP cannot read
calculated-field text and errors on embedded-extract metadata.

Every view except Advanced Comps has the same grain:
`rpt_tableau__state_assessments_dashboard`, one row per student, test code,
administration and results type (actual or preliminary) per academic year (Miami
has one row per FAST window).

### Landing Page

What it shows: the entry point, with navigation to the other views.

Reads: `rpt_tableau__state_assessments_dashboard`.

Worth knowing: it carries no numbers of its own.

### Overview

What it shows: percent proficient by region, school, test and year, with the
city, state and neighborhood comps and the goals from
`int_assessments__academic_goals`.

Reads: `rpt_tableau__state_assessments_dashboard`, including the wide comps
columns `proficiency_city`, `proficiency_state`,
`proficiency_neighborhood_schools` and their `total_students_*` counts.

Worth knowing: those comps columns come from the `state_comps` CTE, which keeps
only `Total` / `All Students` sheet rows and attaches them on year,
`assessment_name`, test code, the enrollment's `school_level`, `season` and
region. Only Spring rows can match, so Miami Fall and Winter FAST windows carry
no comps by design. The CTE takes `avg(percent_proficient)` straight from the
sheet, so an interim figure with no count still shows here.

### Demographics

What it shows: proficiency broken out by student group (race and ethnicity, ML,
IEP, 504, gender, lunch status).

Reads: `rpt_tableau__state_assessments_dashboard`.

Worth knowing: the columns come from two places. `race_ethnicity`, `lep_status`,
`is_504` and `iep_status` come from the NJ state score file on official NJ rows.
They are null on every Miami row, because the Florida leg of
`int_assessments__state_scores` does not carry them, and null on preliminary
rows. So Miami's Demographics view has no race, ML, IEP or 504 breakout.
`gender`, `lunch_status` and the other student attributes come from
`int_extracts__student_enrollments` for every region. Comps here are still
`Total` / `All Students` only; subgroup comps exist only on Advanced Comps.

### Teacher/Student Roster

What it shows: one line per student with their score band per discipline, and
the teacher and course they had.

Reads: `rpt_tableau__state_assessments_dashboard`, including `teacher_name`,
`course_name`, `school_current` and `teacher_name_current`.

Worth knowing: teacher attribution comes from
`base_powerschool__course_enrollments` for the test's year (`teacher_name`) and
for the current year (`teacher_name_current`), one course per credit type
(`ENG`, `MATH`, `SCI`, `SOC`, Miami `SOC` as Civics). The current-year columns
are null until the new year's sections exist. Each student should draw one
full-width colored bar per discipline; a half-colored cell means two rows for
one student and test.

### Proficiency YoY

What it shows: proficiency for the same group across years.

Reads: `rpt_tableau__state_assessments_dashboard`, including
`iready_proficiency_eoy` and `most_recent_grade_level`.

Worth knowing: only a rolling window reaches the workbook
(`academic_year >= current_academic_year - 7`, the current year and the seven
before it); the models underneath keep everything back to PARCC.

### Advanced Comps

What it shows: KTAF against city, state and neighborhood comps, by demographic
subgroup, laid out with the comparison entities as columns.

Grain: `rpt_tableau__state_assessments_dashboard_comps`, one row per academic
year, school level, assessment, test code, region, comparison entity,
demographic group and subgroup (its uniqueness test).

Reads: `rpt_tableau__state_assessments_dashboard_comps`, through three
worksheets (`Advanced Comps - 3-Column`, `- 5-column`, `- Header`). The three
comparison booleans are quick filters on the 3-column sheet, not drawn as marks.

Worth knowing: this is the only view on the comps model, so a change confined to
`rpt_tableau__state_assessments_dashboard_comps` moves no number on the other
views. A comps row with no Region partner renders as an empty Region cell, but
its booleans read `false` (see [Known issues](#known-issues-need-to-fix)).

### Sarba's Report (hidden)

What it shows: not recorded anywhere in the repo. Reads
`rpt_tableau__state_assessments_dashboard`. Ask the workbook owner before
changing or removing it.

## How the models work

### The score view

`rpt_tableau__state_assessments_dashboard` starts from scores and joins students
onto them. The score side is `int_assessments__state_scores` (NJ and Florida
official rows) unioned with preliminary rows from
`int_pearson__student_list_report`. Official rows inner-join
`int_extracts__student_enrollments` on year, `_dbt_source_project` and
`pearson_local_student_identifier` (the network student number despite its
name), with `rn_year = 1` and `grade_level > 2`. A score with no matching
enrollment drops out silently. Goals, schedules, tutoring tier and i-Ready then
left-join on.

### Preliminary scores

The preliminary branch reads Pearson's student list report from 2024 on. It is
gated by `valid_prelim_assessments`, which keeps a year and test type only while
`int_assessments__state_nj_scores` has no Spring row with that
`assessment_name`. Once official scores land, the preliminary rows for that test
drop out on the next build. The two reporting models attach preliminary rows
differently: the score view joins enrollments on the state id
(`state_studentnumber`), while
`int_tableau__state_assessments_demographic_comps` joins on the local id. The
same preliminary score can therefore reach one model and miss the other.

Demographics differ by branch. In the score view, preliminary rows have null
race, ML, IEP and 504. In `int_tableau__state_assessments_demographic_comps`,
preliminary rows take ML status, race and IEP from PowerSchool enrollment while
official NJ rows take them from the state file. Either way, subgroup numbers can
move when official scores replace preliminary ones.

### NJ scores: two vendors in one model

Kipptaf `int_assessments__state_nj_scores` is the one place kipptaf reads NJ
state scores from. It unions two kipptaf passthroughs, each a plain union of the
Newark, Camden and Paterson tables that derives `_dbt_source_project`:

- `int_pearson__all_assessments`: the frozen Pearson history from the district
  pearson package, still under Pearson's column names. The district tables are
  no longer rebuilt.
- `int_cambium__all_assessments`: the live Cambium feed, already mapped to the
  shared names by each district's cambium-package `int_cambium__all_assessments`
  (which reads `stg_cambium__njsla`, carrying NJSLA and the end-of-course tests,
  plus `stg_cambium__njgpa` where the district has it).

What `int_assessments__state_nj_scores` itself does:

- It renames the Pearson columns to the neutral names Cambium already uses
  (`student_number`, `state_student_id`, `student_test_uuid`, `first_name`,
  `last_or_surname`, `administration_round`, `scale_score` and so on), so both
  vendors land in one shape. Never assume a row in it is Pearson.
- It casts `state_student_id` to string.
- The race, ML and IEP mappings are not here. They are written twice, once in
  the pearson package `int_pearson__all_assessments` and once in the cambium
  package `int_cambium__all_assessments`, because neither package can call into
  the other. The Pearson side is frozen, so in practice the Cambium model has to
  keep matching it.
- Cambium reports an abandoned attempt as its own scored row. The cambium
  package model keeps only `test_status = 'completed'`, in both its NJSLA and
  NJGPA branches, so a `pending` row never reaches kipptaf.
  `test_score_complete` (Pearson's `testscorecomplete`) is null on every Cambium
  row, so it cannot do this job.
- After the union, the crosswalk sheet overrides `student_number`, keyed on the
  test UUID, for both vendors:

```sql
coalesce(x.student_number, u.student_number) as student_number,
-- x = stg_google_sheets__pearson__student_crosswalk,
-- joined on u.student_test_uuid = x.student_test_uuid
```

Two grain tests guard it: `student_test_uuid` unique, and `student_number` +
`academic_year` + `aligned_test_code` + `administration_round` unique where
`student_number` is not null (`severity: error`). The UUID is unique per row by
construction, so only the second catches a duplicate attempt; unresolved rows
are excluded because the detector already reports them.

### Repairing a student number

`test_incorrect_student_number_pearson` is the detector. It returns rows from
2017 on whose `student_number` is null or does not match a
`base_powerschool__student_enrollments` row for that year and district
(`rn_year = 1`). It reads `int_assessments__state_nj_scores`, so it covers
Cambium too. It sets no severity and inherits kipptaf's `warn`, so it never
blocks a build. Its failure rows carry `student_test_uuid`, both ids and the
student's name (`first_name`, `last_or_surname`): quote UUIDs and counts only.

The detector cannot see the worst case. A wrong id that happens to be another
valid student number resolves to the wrong student, the join succeeds, and no
test fires. Paterson rows once attached to Newark students this way
([#3956](https://github.com/TEAMSchools/teamster/issues/3956)).

Unmatchable rows cannot be fixed in the sheet. The crosswalk only replaces the
id; the join still needs an enrollment in that year and district. A sheet row
for an unmatchable test does nothing and never expires. A name that resolves
only in another year or district is the signature of this case.

The state id is not a safe fallback. `state_student_id` collides across students
([#3954](https://github.com/TEAMSchools/teamster/issues/3954)), so never add it
as a bare `coalesce` fallback. The tiered matcher uses it only alongside names,
date of birth, enrollment and grade, and proposes rows for a person to accept.
The `stat-dash` skill has the runbook.

### The two comps paths

There are two comps calculations, they read different things, and they disagree
by design. A number that differs between Overview and Advanced Comps is usually
this, not a bug.

- Path one, in the score view. The `state_comps` CTE reads the comps sheet,
  keeps `Total` / `All Students`, and pivots City, State and Neighborhood
  Schools into three wide columns. No subgroups, no KTAF-derived rows. Five
  views use it.
- Path two, the comps model. `rpt_tableau__state_assessments_dashboard_comps`
  unions the sheet rows (minus `SE Accommodation`) with KTAF's own results from
  `int_tableau__state_assessments_demographic_comps`, keeps every subgroup, and
  self-joins each row to its Region partner for the three booleans. Only
  Advanced Comps uses it.

`int_tableau__state_assessments_demographic_comps` computes KTAF proficiency
from student rows with `grouping sets` over region and one demographic at a time
(gender, ethnicity, lunch status, ML, IEP), from 2018 on. It also reads the
comps sheet for `school_level`, `grade_range_band` and `discipline` per test
code, so a test code missing from the sheet loses that metadata. It uses
`school_level_alt` plus hand overrides (Hatch grades 3-4 in 2021-2023, PPES
grade 5 in 2023) to put each score in the band the sheet carries. `school_level`
is not a grouping dimension there, though, so NJ ALG01 taken in middle school
and in high school lands in one row with an arbitrary `school_level`, and only
one of the sheet's MS and HS ALG01 rows can find its Region partner. Florida
splits ALG01 by grade upstream. The comps model fans NJ-wide rows out to Camden,
Newark and Paterson.

The comps model re-derives `percent_proficient` as
`safe_divide(sum(proficient), sum(total))` per group. Where the sheet gave no
count, that is null, so it falls back to the reported percentage when the group
is a single source row. Every group is one source row today; if the grain ever
changes, a count-less group degrades to null rather than averaging percentages
unweighted.

## Supporting models

Shared hubs, one line each:

- `int_assessments__state_scores`: both reporting models read it for official NJ
  and Florida scores, joined on `academic_year`, `_dbt_source_project` and
  `student_number` (as `pearson_local_student_identifier`).
- `int_fldoe__all_assessments`: the Florida leg, read only through
  `int_assessments__state_scores` (`score_source = 'state_fl'`).
- `int_assessments__academic_goals`: the score view reads it for grade, school,
  region and network goals, joined on academic year, `schoolid` and test code.
- `int_extracts__student_enrollments`: both reporting models read it for school,
  grade and student attributes, joined on academic year, `_dbt_source_project`
  and `pearson_local_student_identifier` (state id for preliminary rows),
  `rn_year = 1`.
- `int_extracts__student_enrollments_subjects`: the score view reads it for
  tutoring tier (the test's year) and `iready_proficiency_eoy` (from the row one
  year after the test), joined on year, discipline, student and
  `_dbt_source_project`.
- `base_powerschool__course_enrollments`: the score view reads it for teacher
  and course, joined on year, discipline, student and `_dbt_source_project`.

In-family models with outside children:

- Kipptaf `int_assessments__state_nj_scores` is also read by `dim_assessments`,
  `dim_assessment_administrations`, `int_students__graduation_pathway_scores`,
  `rpt_deanslist__state_test_scores` and `int_assessments__state_scores` (and
  through it, several other score consumers). A change here reaches graduation
  pathways and DeansList as well as STAT.
- The kipptaf `int_pearson__all_assessments` and `int_cambium__all_assessments`
  passthroughs are also read directly by `int_ignite__state_assessment`, which
  skips the crosswalk repair.

## Inputs

Both sheets are Drive-backed external tables. For their location, ask the data
team. The BigQuery MCP cannot read them (no Drive scope); a Python BigQuery
client on application default credentials can, and sees the sheet live. The prod
`stg_` tables are frozen at the last build, so never judge current sheet
contents from them.

### Crosswalk sheet

Two columns, `Student_Test_UUID` and `Student_Number`, one row per test (a
student with four bad test rows needs four rows). Cambium corrections go in the
same tab as Pearson ones. The sheet kept its Pearson name through the vendor
split ([#5591](https://github.com/TEAMSchools/teamster/issues/5591)); renaming
it touches the sheet, its named range, the source entry, the staging model, the
Dagster asset key and the one `ref()` in `int_assessments__state_nj_scores`.

The crosswalk audit (in the `stat-dash` skill) replays every sheet row through
the tiers. The last audit found no row where the rules disagreed with a person,
a few ambiguous rows, and a small number that do not reproduce: some whose
student has no enrollment in the test's year (inert), and some enrolled but
matching no tier, at least one with a date-of-birth mismatch. Those are left
alone on purpose: changing them without knowing why they were entered risks
breaking a correct repair. Look at the date of birth first.

### Comps sheet

<!-- comps sheet: pending owner walkthrough -->

Fourteen columns, one row per academic year, test code, school level, region,
comparison entity and demographic subgroup (a uniqueness test on seven of them
fails the build on a duplicate).

#### Interim comps from media, before the official files

Official comparison files do not arrive in usable form until roughly November.
In the meantime the state's headline results circulate through press coverage
and district decks, and those figures are entered as interim comps so the
dashboard is not blank for the current year. The rule of thumb is that we do not
make rules of comparison, we report what the state reports: an interim figure is
loaded as published, not adjusted or withheld because a year-over-year
comparison would be awkward.

Three things are always true of a media-sourced figure, and they constrain what
it can do.

- There is no denominator. Press figures give a percentage and nothing else, so
  `total_students` is left empty. The comps model falls back to the reported
  percentage, so an interim comp populates all six views. The counts stay empty,
  which is the honest representation of what a press figure contains.
- Only `Total` / `All Students`. Media reporting carries no demographic
  breakouts, so an interim load fills exactly one demographic row per test code
  and region. Every subgroup row waits for the official file.
- ALG01 arrives mixed. Media figures never separate Algebra I taken in middle
  school from Algebra I taken in high school; one combined number is published.
  The interim convention is to write that same figure to both the MS and the HS
  `school_level` rows, with `remove_row = FALSE` on both. This is deliberately
  imprecise and known to be so: the weighted MS/HS rollup that `remove_row`
  exists to build needs counts, which an interim load does not have. It is
  corrected when the official file lands.

When the official file arrives for a year that already has interim rows, replace
the whole tab rather than the interim rows one by one; the procedure is in the
`stat-dash` skill.

#### A missing value means the state did not provide it

That is the whole rule. `total_students` empty does not mark a row as
provisional, second-rate or media-sourced; it means the state published a
percentage and no count for that cell. It happens in press figures, which almost
never carry counts, and it happens in official files, which sometimes omit them
for a particular subgroup. Same cause, one rule.

So do not infer provenance from a null. Some AY2024 official rows are missing a
denominator for one subgroup, and nothing in the row distinguishes them from a
press figure. To see which rows are affected, ask the sheet rather than trusting
a list (run it through application default credentials, not the BigQuery MCP):

```sql
select
    academic_year,
    region,
    comparison_entity,
    count(*) as rows_affected,
    count(distinct aligned_test_code) as test_codes,
    string_agg(distinct comparison_demographic_subgroup) as subgroups,
from kipptaf_google_sheets.src_google_sheets__state_test_comparison_demographics
where total_students is null and percent_proficient is not null
group by academic_year, region, comparison_entity
order by academic_year desc, region, comparison_entity
```

#### Controlled vocabulary

`comparison_demographic_subgroup`, after the normalization in
`stg_google_sheets__state_test_comparison_demographics`:

`African American` · `All Students` · `American Indian` · `Asian` ·
`Economically Disadvantaged` · `Female` · `Hispanic` · `Male` · `ML` ·
`Native Hawaiian` · `Non Economically Disadvantaged` · `Other` ·
`SE Accommodation` · `Students With Disabilities` · `White`

Guarded by an `accepted_values` test at `severity: error`. Extend it
deliberately when a genuinely new subgroup appears, never to make a build pass.
The staging model rewrites two older sheet spellings
(`Black Or African American`, `Non-Econ. Disadvantaged`) because the Region
self-join matches on the exact string; a new variant would silently turn every
comparison for that subgroup `false`.

Test codes carried by the sheet: `ELA03`-`ELA10`, `ELAGP`, `MAT03`-`MAT08`,
`MATGP`, `ALG01`, `ALG02`, `GEO01`, `SCI05`, `SCI08`, `SCI11`, `SOC08`.

#### ALG01 and `remove_row`

`ALG01` is the awkward one. Overall comparisons split MS from HS, but official
sources publish demographic breakdowns only for grades 8+ combined. The sheet
therefore carries HS-only ALG01 rows flagged `remove_row = TRUE`, which the
staging model filters out of the main rows and re-aggregates in a second branch
into a single weighted `Total` / `All Students` row. `ALG02` totals are 10th
grade only and `GEO01` follows the same pattern for grades 9 and 10, while their
demographic rows include every student who took the test.

## Decisions

- Scores are the left table; enrollments join onto them. A score with no
  enrollment in its own year and district does not appear. That is why the
  crosswalk and the detector exist.
- The detector stays `warn`. Some of what it flags can never be fixed; an
  `error` would block every deploy on a condition nobody can clear.
- No state-id fallback in the model. Done safely it is the whole tiered matcher,
  for a population a person clears in minutes. The matcher proposes; a person
  accepts.
- The comps model falls back to the reported percentage instead of adding a
  "preliminary" flag to the sheet. `total_students is null` already identifies
  those rows, and a second hand-kept flag could disagree with no test to catch
  it.
- The comparison booleans keep `if(x, true, false)`, which turns "no partner"
  into `false`. Changing it would move rows out of saved `False` filter
  selections; that is the workbook owner's call.
- The exposure carries the Tableau LSID and no `url`. The LSID identifies the
  workbook; a made-up `url` is worse than none.
- The preliminary branch gates itself on official scores landing, so nobody
  comments it in or out by hand.
- Rolling window (the current year and the seven before it). Old defects outside
  it are invisible to users and not worth fixing; check the year before chasing
  a flagged row.

## Known issues, need to fix

Run these read-only in BigQuery. Report counts only.

### Comparisons with no Region partner read `false`

About a third of the non-Region rows in the comps model have no Region partner,
nearly all subgroups where KTAF had no students (for example `Asian`, `White`).
On Advanced Comps they render as an empty Region cell, which is right. But the
three booleans read `false`, not null, so picking `False` in the quick filter
mixes real losses with rows that had nothing to compare.

```sql
with
    c as (
        select *,
        from kipptaf_tableau.rpt_tableau__state_assessments_dashboard_comps
    ),

    r as (select *, from c where comparison_entity = 'Region')

select
    countif(c.comparison_entity != 'Region') as non_region_rows,
    countif(
        c.comparison_entity != 'Region' and r.region is null
    ) as no_region_partner,
from c
left join
    r
    on c.academic_year = r.academic_year
    and c.school_level = r.school_level
    and c.grade_range_band = r.grade_range_band
    and c.assessment_name = r.assessment_name
    and c.discipline = r.discipline
    and c.test_code = r.test_code
    and c.region = r.region
    and c.comparison_demographic_group = r.comparison_demographic_group
    and c.comparison_demographic_subgroup = r.comparison_demographic_subgroup
```

The fix is to drop the three `if(..., true, false)` wrappers so the filter gets
a null. Owner's decision, see [Decisions](#decisions).

### Official comparison data stops at AY2024

The sheet has official rows through academic year 2024. AY2025 holds only
interim NJ statewide `Total` / `All Students` rows with no counts; no City,
Miami or subgroup rows. NJ has no 2019 or 2020 rows (COVID) and Paterson starts
at 2023.

```sql
select
    academic_year,
    region,
    comparison_entity,
    count(*) as sheet_rows,
    countif(total_students is null) as no_denominator,
    countif(comparison_demographic_subgroup != 'All Students') as subgroup_rows,
from kipptaf_google_sheets.stg_google_sheets__state_test_comparison_demographics
where academic_year >= 2024
group by academic_year, region, comparison_entity
order by academic_year, region, comparison_entity
```

This reads the prod staging table, which lags the sheet; confirm against the
live external before acting.

### Prior-year school attribution can move

A closed year's school attribution comes from whichever enrollment row wins
`rn_year = 1` for that year today. When PowerSchool enrollment records are
edited or re-dated after the year ends, or a student number is merged, a
prior-year score moves to another school. Most affected records have been
restored in PowerSchool; the Tableau extract must be refreshed to show it. There
is no regression guard (a snapshot or test asserting that closed-year counts per
school and test do not change). Tracked in
[#5404](https://github.com/TEAMSchools/teamster/issues/5404).

### Detector rows outstanding

`test_incorrect_student_number_pearson` warns on a handful of rows: unmatchable
rows from academic years 2017 and 2018, outside the rolling window, and a few
AY2025 Cambium rows with an absent local id. The old rows need an Ops look at
enrollment history, not a sheet row; the Cambium ones take a crosswalk row after
the tiered match. Tracked in
[#3814](https://github.com/TEAMSchools/teamster/issues/3814).

```sql
select
    a.academic_year,
    a.student_number is null as local_id_absent,
    count(*) as flagged_rows,
from kipptaf_assessments.int_assessments__state_nj_scores as a
left join
    kipptaf_powerschool.base_powerschool__student_enrollments as e
    on a.student_number = e.student_number
    and a.academic_year = e.academic_year
    and a._dbt_source_project = e._dbt_source_project
    and e.rn_year = 1
where
    a.academic_year >= 2017
    and (e.student_number is null or a.student_number is null)
group by a.academic_year, local_id_absent
order by a.academic_year
```

### No preliminary feed after the vendor change

The preliminary branch reads only Pearson's student list report. Nothing from
Cambium feeds it, so from Spring 2026 there are no preliminary rows and the
branch is dormant. Whether Cambium publishes an equivalent early file is not
known. Shown by the code: both `prelim_assessments` CTEs read
`int_pearson__student_list_report`, which reads
`stg_pearson__student_list_report`.

### Planned refactors

- [#5591](https://github.com/TEAMSchools/teamster/issues/5591) is done: the
  Pearson models are frozen, the Cambium mapping lives in the cambium package,
  and every kipptaf reader uses `int_assessments__state_nj_scores`.
- [#5496](https://github.com/TEAMSchools/teamster/issues/5496) is still open,
  but its main ask, Cambium's column names as the NJ standard, now holds in
  `int_assessments__state_nj_scores`. Check what is left before picking it up.

## Yearly upkeep

After any model change, refresh the Tableau extracts: the exposure has no
Dagster refresh schedule, so the workbook shows nothing new until Tableau Server
refreshes.

### July: academic-year rollover

- The rolling window moves on its own when `current_academic_year` bumps.
- Teacher columns for the current year (`school_current`,
  `teacher_name_current`) are null on the roster until the new year's
  PowerSchool sections exist. Expected.
- Comps for the new year do not exist yet; comps columns stay empty for it.

### Spring: preliminary scores

This procedure comes from the 2023 design notes and is not verified against
current practice; confirm with the owner.

1. Preliminary student list files are dropped on the data team's SFTP
   (`student_list_report` folder per region); ask the data team for the path.
2. The model picks them up automatically while no official scores exist for that
   test and year.
3. In Tableau Desktop, set the Results Type filter to show both Actual and
   Preliminary.
4. Publish that version to a restricted folder, never to Production.

See
[No preliminary feed after the vendor change](#no-preliminary-feed-after-the-vendor-change)
before relying on this for Spring 2026 and later.

### After every Cambium load

Check the score view's grain test and the detector. A failure of the second
grain test on `int_assessments__state_nj_scores`, or of the uniqueness test on
`rpt_tableau__state_assessments_dashboard`, is a duplicate attempt arriving;
read the failing rows rather than re-running the build. Clear new absent-id rows
through the tiered match and the crosswalk sheet (runbook in the `stat-dash`
skill).

### Summer to November: comps

Load interim media comps for the new year as figures circulate, then replace the
year with the official comparison file when it arrives (see
[Comps sheet](#comps-sheet) and the `stat-dash` skill). Confirm the counts
arrived after the swap.
