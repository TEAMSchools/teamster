# Pass/fail courses in PowerSchool

Refs [#5092](https://github.com/TEAMSchools/teamster/issues/5092)

## Problem

Schools want pass/fail courses. A pass/fail course must print `P` or `F` on
report cards and transcripts, earn credit toward graduation, and stay out of
every GPA calculation.

The only PowerSchool setting that keeps a course out of GPA is
`courses.excludefromgpa`. PowerSchool itself computes the GPA, class rank, and
honor roll that print on report cards and transcripts, so that flag has to be
set. There is no alternative lever.

But the dbt models give that flag a second, unrelated job. Eight models filter
or branch on the flag. Four of those use it for GPA arithmetic, which is
correct. The other 4 use `exclude_from_gpa = 0` as a row-population filter
meaning "this is a real class." That works today only because the flag is set
exclusively on non-instructional containers.

A credit-bearing pass/fail course flagged `excludefromgpa = 1` therefore
inherits the "not a real class" treatment and vanishes from reporting it belongs
in.

### The coupling in one line

`base_powerschool__final_grades` derives a single column:

```sql
coalesce(sg_exclude_from_gpa, courses_excludefromgpa) as exclude_from_gpa
```

Models downstream read that column for two different purposes: GPA arithmetic,
and "is this row a real course."

Two caveats on "single". `int_students__final_grades.sql:109` independently
derives the same column for the Focus branch as `if(g.affects_gpa = 'Y', 0, 1)`.
And several models bypass it entirely, reading `storedgrades.excludefromgpa` or
the raw `courses.excludefromgpa` directly. See _The raw-column path_ below.

## Goals

A pass/fail course must:

1. Print `P` or `F` on report cards and transcripts.
1. Earn credit toward graduation, including mid-year, before grades store.
1. Contribute nothing to any GPA: term, semester, `Y1`, cumulative, projected,
   core, weighted, or unweighted.
1. Count as a failure when failed.
1. Appear on the DeansList transcript extract.
1. Appear on the high school early warning dashboard.

## Non-goals

- **Gradebook audit scope.** Pass/fail sections stay out of the gradebook audit,
  and the 2 audit filters are left untouched. Read the reason carefully, because
  it is a trap: those filters read a column named `exclude_from_gpa` that is
  sourced from the **raw** `courses.excludefromgpa`, not from
  `base_powerschool__final_grades`. It stays `1` for a pass/fail course, so the
  exclusion holds for free. It is a different column from the one
  `is_graded_course` derives from, despite the shared name. Anyone who later
  "unifies" the audit filters onto `is_graded_course` for consistency will
  silently invert this non-goal and pull every pass/fail section, plus Homeroom,
  into the audit. See _The raw-column path_.
- **Miami.** Miami runs on Focus, not PowerSchool. The Focus branch gets an
  explicit `false` and a comment.
- **Honor roll and class rank.** No dbt model reads `excludefromclassrank` or
  `excludefromhonorroll`. PowerSchool computes both natively.

## Evidence

Every number below was measured against the warehouse on 2026-08-31, not
assumed.

### The flag is currently synonymous with "not a real class"

Current-year rows in `kipptaf_powerschool.base_powerschool__final_grades`:

| Region   | Courses with `exclude_from_gpa = 1`    | Credit-bearing rows |
| -------- | -------------------------------------- | ------------------- |
| Newark   | Lunch, HR, Early Dismissal, Study Hall | 0                   |
| Camden   | Lunch, HR, Early Dismissal             | 0                   |
| Paterson | HR                                     | 0                   |

Zero credit-bearing rows in all 3 regions. That is why the proxy has held.

### A pass/fail grade scale already exists

`int_powerschool__gradescaleitem_lookup` shows a scale named `Pass Fail Scale`
in Newark and Camden, `gradescaleid` 346:

| Letter | `grade_points` | Cutoff range |
| ------ | -------------- | ------------ |
| `F`    | 0              | 0 to 59.9    |
| `P`    | 0              | 60 to 999.9  |

**Both letters carry `grade_points = 0`.** That is exactly why `excludefromgpa`
is load-bearing: without it, every `P` scores 0.0 grade points against real
credit hours and craters the GPA.

Paterson has no such scale and needs one created with the same name. Miami is
out of scope.

### The scale is already attached to a non-course, and that blocks this design

**Camden `HR` (Homeroom) sits on scale 346 at the course level.** Measured in
`kipptaf_powerschool.base_powerschool__sections`: 101 sections in
`terms_yearid = 36`, 102 in `terms_yearid = 35`, with
`sections_gradescaleid = 0` so the resolved scale is 346.

Camden `HR` is the **only** current-year course on scale 346 in any region.

This falsifies the naive form of this design. Keying `is_pass_fail` on the scale
name alone marks Camden Homeroom as pass/fail, which flips `is_graded_course`
true for 8672 current-year final-grade rows and pushes Homeroom onto Camden
transcripts through repoint 4 and onto the early warning dashboard through
repoint 3. Neither
`kipptaf/models/extracts/deanslist/properties/rpt_deanslist__transcript_grades.yml`
nor
`kipptaf/models/extracts/tableau/properties/rpt_tableau__hs_early_warning_dashboard.yml`
declares any `data_tests`, so nothing would catch it.

The resolution is a PowerSchool data change, recorded as a blocking prerequisite
below.

### Section-level grade scale overrides are unused today

`sections.gradescaleid` is staged but never read. Every dbt model resolves the
scale from `courses.gradescaleid`. Divergence in
`kipptaf_powerschool.base_powerschool__sections`:

| Region   | Current-year sections, `terms_yearid = 36` | Section scale differs from course |
| -------- | ------------------------------------------ | --------------------------------- |
| Newark   | 1824                                       | 0                                 |
| Camden   | 688                                        | 0                                 |
| Paterson | 140                                        | 0                                 |
| Miami    | 0 applicable                               | 0                                 |

`0` is PowerSchool's inherit-from-course sentinel and every current-year section
carries it. Divergence is confined to prior years, but it is **not** cleaned up:
1299 sections all-time, including 27 live rows in Paterson `terms_yearid = 35`
and 27 more in `terms_yearid = 34`, all `sections_gradescaleid = 278` over
courses on 17 or 487. Commit 1's conclusion holds for the current year, which is
all `base_powerschool__final_grades` can see. Any future model that resolves a
scale for a prior year inherits a real behavior change for those 54 sections.

Four historical Newark sections carried scale 346 on a course with scale 874.
Section-level pass/fail is therefore not hypothetical, which is why the design
supports it.

### The unweighted CASE has a dead branch

`base_powerschool__sections.sql` contains:

```sql
case cou.gradescaleid
    when 991 then 976
    when 712 then 874
    /* MISSING GRADESCALE - default 2016+ */
    when null then 874
    else cou.gradescaleid
end
```

`case X when null` compares `X = NULL`, which is never true, so the branch is
dead. Verified: all 843 rows with a null course scale produce a null unweighted
scale, not `874`. All 843 are Focus rows from
`kippmiami_focus.int_focus__course_periods`, so the dead branch never mattered.
Dropping it is provably behavior-preserving.

### One model needs no change, but is not correct today

`int_powerschool__final_grades_rollup` applies no exclusion filter at all. It
sums `potential_credit_hours` and counts `F` and `F*` across every final-grade
row. Non-instructional containers carry 0 credit hours, so the credit sums are
unaffected and `projected_credits_y1_term` and the 25/50/85/120 credit gates in
`int_reporting__promotional_status` need no change.

The failure counts are a different story, and the earlier draft of this spec had
this wrong. Containers do **not** all carry null letter grades. Measured on
current-year rows with `exclude_from_gpa = 1`:

| Region | Course       | Rows  | Non-null `y1_letter_grade_adjusted` | `F` or `F*` |
| ------ | ------------ | ----- | ----------------------------------- | ----------- |
| Camden | `HR`         | 8672  | 72                                  | 4           |
| Newark | `HR`         | 27272 | 92                                  | 0           |
| Newark | `Study Hall` | 1584  | 212                                 | 0           |

So `n_failing` in `int_powerschool__final_grades_rollup` **already over-counts 4
Camden Homeroom failures** into `int_reporting__promotional_status`. That is a
pre-existing defect, not one this work introduces, and it is out of scope here.
It is recorded so nobody reads the 0-differing-rows gate as proof the model is
correct.

`int_students__athletic_eligibility` counts `F` and `F*` from
`base_powerschool__final_grades` with no exclusion filter, so those same
Homeroom failures already affect eligibility. Also pre-existing, also out of
scope.

## PowerSchool configuration recipe

Per course, for a credit-bearing pass/fail course:

| Field                     | Value                           | Why                                                                      |
| ------------------------- | ------------------------------- | ------------------------------------------------------------------------ |
| `gradescaleid`            | a scale named `Pass Fail Scale` | Prints `P` or `F`, and is the fact dbt reads to identify pass/fail       |
| `excludefromgpa`          | `1`                             | The only lever PowerSchool honors. Both `P` and `F` carry 0 grade points |
| `excludefromclassrank`    | `1`                             | Class rank prints on transcripts                                         |
| `excludefromhonorroll`    | `1`                             | Same                                                                     |
| `credit_hours`            | greater than 0                  | Required for credit toward graduation                                    |
| `excludefromstoredgrades` | `0`                             | Grades must store to reach the transcript                                |
| `excludefromgraduation`   | `0` at store time               | Credits count toward graduation                                          |
| `credittype`              | the real subject                | See below                                                                |

**Do not invent a `PF` credit type.** `credittype` drives the core-GPA filter
`credit_type in ('MATH', 'SCI', 'ENG', 'SOC')` in
`int_powerschool__gpa_cumulative`, the `n_failing_core` calculation in
`int_powerschool__final_grades_rollup`, and graduation-requirement subject
mapping. A pass/fail English course keeps `credittype = 'ENG'`.

Paterson must create a scale named `Pass Fail Scale`. Keying on name rather than
id is deliberate: the regions are separate PowerSchool instances and ids do not
align across them.

## Blocking prerequisite: move Camden Homeroom off scale 346

**Commit 2 must not ship until this is done.** It is a PowerSchool data change,
not a code change, and it is owned by Ops rather than the data team.

Camden `HR` must move from `gradescaleid` 346 (`Pass Fail Scale`) to 976
(`KIPP NJ 2019 (5-12) Unweighted`).

Why 976: Newark `HR` already uses it, as do Newark `Early Dismissal`, Newark
`Study Hall`, and Camden `Lunch`. The change aligns Camden Homeroom with the
scale every other Homeroom and container course in New Jersey already uses.
Camden `HR` carries 0 credit hours and `excludefromgpa = 1`, so no GPA, credit,
or transcript value depends on its scale today.

Scope: 1 course record, 101 current-year sections. Camden `HR` is the only
current-year course on scale 346 in any region, so this is the complete fix.

Sequencing. Commit 1 is safe to ship before the PowerSchool change, because it
does not read the scale name. Commit 2 is not: shipping it while Camden `HR`
still resolves to 346 puts Homeroom on Camden transcripts.

The alternative considered and rejected: adding `and cou.credit_hours > 0` to
the `is_pass_fail` definition, which also excludes Camden `HR`. Rejected because
it changes what pass/fail means in the model rather than fixing the underlying
data. The guard test below covers the recurrence risk instead.

## Commit 1: resolve the grade scale from the section

This commit must move no data. It exists so that pass/fail lands on a foundation
where the scale dbt reads matches the scale PowerSchool printed from.

### Why it is needed

If dbt only ever reads the course scale, section-level pass/fail is a silent
trap. Someone sets `Pass Fail Scale` on a section, PowerSchool prints `P`, and
dbt keeps computing A-to-F grade points off the course scale. The two disagree
with no error anywhere.

### Changes

In `base_powerschool__sections.sql`, add:

```sql
coalesce(nullif(sec.gradescaleid, 0), cou.gradescaleid) as gradescaleid_resolved,
```

Rename `courses_gradescaleid_unweighted` to `gradescaleid_unweighted_resolved`
and compute it over the resolved id, dropping the dead null branch:

```sql
case coalesce(nullif(sec.gradescaleid, 0), cou.gradescaleid)
    /* unweighted 2019+ */
    when 991
    then 976
    /* unweighted 2016-2018 */
    when 712
    then 874
    else coalesce(nullif(sec.gradescaleid, 0), cou.gradescaleid)
end as gradescaleid_unweighted_resolved,
```

The rename is deliberate rather than an added alias. The `courses_` prefix is
generated by `dbt_utils.star` for genuine passthroughs, and
`courses_gradescaleid_unweighted` is a hand-derived column borrowing that
prefix. Keeping both names would let a future reader pick the wrong one. The raw
`sections_gradescaleid` and `courses_gradescaleid` passthroughs are untouched.

### The 9 resolution sites to repoint, and 2 columns to add

| File                                                                      | Line  | Current                               | Becomes                                |
| ------------------------------------------------------------------------- | ----- | ------------------------------------- | -------------------------------------- |
| `powerschool/models/sis/base/base_powerschool__sections.sql`              | 34-46 | the unweighted CASE                   | as above                               |
| `powerschool/models/sis/base/base_powerschool__final_grades.sql`          | 19    | `enr.courses_gradescaleid_unweighted` | `enr.gradescaleid_unweighted_resolved` |
| `powerschool/models/sis/base/base_powerschool__final_grades.sql`          | 118   | `et.courses_gradescaleid`             | `et.gradescaleid_resolved`             |
| `powerschool/models/sis/base/base_powerschool__final_grades.sql`          | 127   | `et.courses_gradescaleid`             | `et.gradescaleid_resolved`             |
| `powerschool/models/sis/base/base_powerschool__final_grades.sql`          | 276   | `y1.courses_gradescaleid_unweighted`  | `y1.gradescaleid_unweighted_resolved`  |
| `powerschool/models/sis/base/base_powerschool__final_grades.sql`          | 343   | `y1.courses_gradescaleid`             | `y1.gradescaleid_resolved`             |
| `powerschool/models/sis/base/base_powerschool__final_grades.sql`          | 348   | `y1.courses_gradescaleid_unweighted`  | `y1.gradescaleid_unweighted_resolved`  |
| `powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql` | 110   | `fg.courses_gradescaleid_unweighted`  | `fg.gradescaleid_unweighted_resolved`  |
| `kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`  | 1082  | `qg.courses_gradescaleid`             | `qg.gradescaleid_resolved`             |

**Two columns must also be ADDED, not just renamed.** For lines 118, 127, and
343 to resolve `et.gradescaleid_resolved` and `y1.gradescaleid_resolved`, the
new column has to be carried through the CTEs alongside the existing
`courses_gradescaleid` selections at `base_powerschool__final_grades.sql:18`
(`enr_termbins`) and `:275` (final select). Omitting either fails the build,
which is the loud failure mode.

`base_powerschool__course_enrollments` picks up the new columns automatically
through `dbt_utils.star`. `rpt_tableau__student_course_grades` also selects
`courses_gradescaleid` at lines 595, 628, and 664, which must follow.

### The rename sweep

Use `--include='*.{sql,yml,md}'`, per the repo rule that a model or column
rename must sweep markdown too. Specifically:

- 4 `properties/*.yml` files document the column:
  `base_powerschool__sections.yml` line 391,
  `base_powerschool__course_enrollments.yml` line 416,
  `base_powerschool__final_grades.yml` line 62, and the `kipptaf` copy at
  `kipptaf/models/powerschool/base/properties/base_powerschool__final_grades.yml`
  line 150.
- 6 unit-test fixture blocks in
  `powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml`
  set `courses_gradescaleid_unweighted`, at lines 294, 309, 324, 339, 354,
  and 369.

### New tests

1. **Warn severity.** Flag any section whose resolved scale differs from its
   course scale. A section override is legitimate, but it moves GPA for those
   students, so it should surface in CI rather than silently.
1. **Error severity, added with commit 2.** Fail if any course on a pass/fail
   scale has `credit_hours = 0`. This is the guard against the Camden Homeroom
   problem recurring. Once Ops moves Camden `HR` off 346 the test passes, and it
   fails the build the next time a container course is put on a pass/fail scale
   rather than letting Homeroom reach a transcript. This test is the reason the
   `credit_hours > 0` conjunct is not needed in the `is_pass_fail` definition
   itself.

## Commit 2: identify pass/fail and repoint 4 filters

### Where pass/fail is determined

Inline in `base_powerschool__sections.sql`, joined to the parent grade-scale
rows and keyed on name:

```sql
{# TODO: refactor to gsheet #}
coalesce(gs.name in ('Pass Fail Scale'), false) as is_pass_fail,
```

joined via:

```sql
left join
    {{ ref("stg_powerschool__gradescaleitem") }} as gs
    on coalesce(nullif(sec.gradescaleid, 0), cou.gradescaleid) = gs.id
    and gs.gradescaleid = -1
```

`gradescaleid = -1` selects parent scale rows rather than the individual letter
items, which is the same filter `int_powerschool__gradescaleitem_lookup` already
uses.

This sits beside the existing hardcoded unweighted CASE, which carries the same
`TODO: refactor to gsheet` marker, so it matches local precedent.

**Rejected alternatives.** A CSV seed: the repo contains no seeds at all,
despite `seed-paths` being configured in all 16 projects, so this would
establish a new convention for one row of data. A Google Sheets crosswalk: all
13 existing crosswalks live in `kipptaf`, and the GPA models that need this
column live in the `powerschool` package, which cannot reference `kipptaf`. A
PowerSchool course custom field: needs page customization, a new source table, a
staging model with a contract, 4 district configs, and per-course data entry
that can contradict the grade scale, giving 2 sources of truth.

### New columns

`base_powerschool__sections` gains `is_pass_fail`, flowing into
`base_powerschool__course_enrollments` through `dbt_utils.star`.

`base_powerschool__final_grades` passes `is_pass_fail` through and adds:

```sql
(exclude_from_gpa = 0 or is_pass_fail) as is_graded_course,
```

`is_graded_course` means "carries a real grade," as against Lunch, HR, Early
Dismissal, and Study Hall.

**There are 2 derivation sites for `is_pass_fail`, not 1.** The current-year
path resolves it from `base_powerschool__sections` as above. The prior-year path
cannot: `int_powerschool__gpa_term`'s prior-year branch reads
`stg_powerschool__storedgrades`, `stg_powerschool__courses`, and
`int_powerschool__gradescaleitem_lookup`, and never touches
`base_powerschool__sections` or `base_powerschool__final_grades`, so neither new
column is in scope there. It must derive pass/fail independently from
`stg_powerschool__storedgrades.gradescale_name`, which carries the scale name
directly. Both sites must use the same name list; a shared macro or a single
`int_` lookup model is the way to keep them honest.

### Repoint 1: failure counts

`int_powerschool__gpa_term.sql` line 112 computes:

```sql
sum(if(y1_letter_grade like 'F%', 1, 0)) as n_failing_y1,
```

inside `grade_rollup`, which reads `grade_detail`. `grade_detail` filters
`where exclude_from_gpa = 0 and potential_credit_hours > 0`, so pass/fail rows
never arrive.

**Do not widen that filter.** Widening it pulls pass/fail rows into
`total_credit_hours_term`, `total_credit_hours_y1`, `grade_avg_term`,
`grade_avg_y1`, and both GPA numerators, leaving 6 columns that would each need
nulling. One miss silently moves a GPA.

Instead add a separate `failing_detail` CTE over the wider population, covering
both the current-year and prior-year branches. See _New columns_ above: the
prior-year branch needs its own `is_pass_fail` derivation from
`stg_powerschool__storedgrades.gradescale_name`.

Three details decide whether this works.

**`failing_detail` retains `potential_credit_hours > 0`.** This is not optional.
Dropping it admits 49485 current-year rows that have `exclude_from_gpa = 0` and
`potential_credit_hours <= 0`. None are failing today, so the verification gate
would return 0 and the number would then drift silently as Y1 letter grades
populate through the year. Keeping the predicate also means a 0-credit container
can never contribute a failure, which is the intent.

**The grain is `(studentid, schoolid, yearid, storecode, is_current)` — 5
columns, matching `grade_rollup`'s `group by` exactly.** A 4-column grain
omitting `is_current` happens to work today (0 of 22082 current-year groups span
more than one `is_current` value, and the prior-year branch derives `is_current`
as a pure function of `storecode`), but that is an empirical property of the
data, not a structural guarantee. Match the group-by instead of relying on it.

**`grade_rollup` is itself the aggregate**, so `failing_detail` joins in its
`FROM` and `n_failing_y1` must be read with `any_value()` or `max()`, never
`sum()`, or it multiplies across the group.

`grade_detail` is untouched, so no GPA column can move by construction. One
consequence worth stating: `grade_rollup` reads only `grade_detail`, so a
left-joined `failing_detail` adds no rows. A student whose entire schedule is
pass/fail produces no `grade_rollup` row at all, and goal 4 is therefore not met
for that student. It is an edge case, not a blocker, but it should be recorded
rather than discovered.

Pass/fail percents stay out of `grade_avg_term` and `grade_avg_y1`. A pass/fail
course has a real underlying percent but its reported grade is `P`, so including
it would change a grade average that nobody asked to change.

### Repoint 2: projected credits

`int_powerschool__gpa_cumulative.sql` has a `grades_union` of 3 branches. The
current-year branch filters `where fg.exclude_from_gpa = 0` at line 112 and the
semester-1 branch at line 166. The current-year branch is also where
`earnedcrhrs_projected` comes from.

This is a defect that predates pass/fail. Prior-year credits key on
`excludefromgraduation`, but current-year projected credits key on GPA
exclusion. Any course excluded from GPA loses its credits from projections all
year, then gains them back once grades store.

Add a **4th union branch** for current-year pass/fail rows contributing only
`earnedcrhrs_projected` and `earnedcrhrs_projected_s1`, with every GPA point and
potential-credit column null. Each existing branch already fills a subset of
columns and nulls the rest, so this matches the model's shape.

`potentialcrhrs_projected` must stay clean. It is both the GPA denominator in
`cumulative_y1_gpa_projected` and the input to `potentialcrhrs_current`, which
feeds `gpa_needed_for_cumulative_3_0` and the
`potentialcrhrs_current_max_known_unweighted` equality guard behind
`is_cumulative_3_0_attainable`. Pass/fail credits must never enter it.

**The new branch must join `base_powerschool__student_enrollments` with
`co.rn_year = 1` and take `schoolid` from it**, exactly as branches 2 and 3 do
at lines 97-101 and 152-156. `points_rollup` groups by `(studentid, schoolid)`
at line 273, so two things go wrong otherwise: omitting `rn_year = 1` fans out a
multi-stint student and inflates `earned_credits_cum_projected`, and taking
`schoolid` from anywhere else lands the new rows in a different group so credits
split across 2 output rows instead of augmenting the existing one.

**A student whose only current-year rows are pass/fail produces a NEW output
row** with every GPA column null. That is a fourth kind of change beyond the 3
moving columns listed under _Verification_, and it breaks
`powerschool/tests/test_int_powerschool__gpa_cumulative_year__reconciles_stored.sql`:
the inner join at lines 28-31 newly matches, `gc.cumulative_y1_gpa` is null, and
the `coalesce(..., -99)` comparison exceeds the 0.015 tolerance. Either the test
needs a guard for null projected GPA, or the branch needs to suppress rows for
students with no other current-year enrollment. Decide before implementing.

Minor: an `earnedcrhrs_projected` of `0.0` turns a previously-null `sum()` into
`0.0` for a student with no branch-2 rows. Harmless for totals, visible in a
strict diff.

### Repoints 3 and 4: extracts

| File                                                                          | Line | Current                       | Becomes                   |
| ----------------------------------------------------------------------------- | ---- | ----------------------------- | ------------------------- |
| `kipptaf/models/extracts/tableau/rpt_tableau__hs_early_warning_dashboard.sql` | 90   | `and gr.exclude_from_gpa = 0` | `and gr.is_graded_course` |
| `kipptaf/models/extracts/deanslist/rpt_deanslist__transcript_grades.sql`      | 57   | `and fg.exclude_from_gpa = 0` | `and fg.is_graded_course` |

### kipptaf propagation

**The kipptaf chain is not a simple star.** `kipptaf`'s
`base_powerschool__sections` and `base_powerschool__course_enrollments` are
compatibility passthroughs over `int_students__course_sections` and
`int_students__course_enrollments`. The real path is district
`base_powerschool__sections` -> `int_powerschool__sections_union`
(`dbt_utils.union_relations`, resolved at compile time against the live prod
relations) -> `int_students__course_sections` (`sec.*`) -> passthrough. Two
consequences:

- **Ship in 2 PRs: district first, then kipptaf**, per the _kipptaf source
  consumers of district columns_ rule in `src/dbt/CLAUDE.md`. The new columns
  reach kipptaf only after each district's prod relation carries them.
- **`is_pass_fail` will be NULL, not `false`**, on the Focus branch of
  `int_students__course_sections` and on the frozen `kippmiami_powerschool`
  archive rows that `union_relations` null-fills. Set it explicitly to `false`
  on the Focus branch. Any predicate reading it must be null-safe.

Worth knowing: `int_students__course_sections` already derives `is_homeroom` as
`sections_course_number like 'HR%'`. That is an existing purpose-built container
flag and a precedent for naming the concept directly rather than inferring it
from a GPA setting.

`int_students__final_grades.sql` carries `is_pass_fail` on the PowerSchool
branch and hardcodes `false` on the Focus branch, with a comment recording that
Miami is out of scope.

`fct_grades_term.sql` adds `is_pass_fail` beside the existing
`is_excluded_from_gpa`. Without it, a mart consumer sees a course excluded from
GPA and cannot tell whether it is a pass/fail class or lunch. This is a contract
addition on a model exposed to Cube, so it needs a
`properties/fct_grades_term.yml` entry with `data_type: boolean` and a
description, following the `is_excluded_from_gpa` entry at line 184.
`fct_grades_term` is contract-enforced through
`kipptaf/dbt_project.yml:212-215`, so a missing yml entry fails the build.

`rpt_tableau__gradebook_gpa.sql` and `rpt_tableau__student_course_grades.sql`
also add `is_pass_fail` alongside the `exclude_from_gpa` dimension they already
expose. The argument is the same one that justifies the `fct_grades_term`
addition, and these are the models school leaders actually open. Both read the
raw course flag, so they take `is_pass_fail` from the same source rather than
from `is_graded_course`.

## Downstream inventory

Complete list of everything that reads the flag, so nothing is missed.

### Models that filter on it

| Model                                               | Purpose of the filter           | Action                          |
| --------------------------------------------------- | ------------------------------- | ------------------------------- |
| `int_powerschool__gpa_term`, main filter            | GPA arithmetic                  | unchanged                       |
| `int_powerschool__gpa_term`, `n_failing_y1`         | failure count                   | repoint 1                       |
| `int_powerschool__gpa_term`, prior-year branch      | GPA arithmetic                  | unchanged, covered by repoint 1 |
| `int_powerschool__gpa_cumulative`, point sums       | GPA arithmetic                  | unchanged                       |
| `int_powerschool__gpa_cumulative`, current-year, S1 | gates credits too               | repoint 2                       |
| `int_powerschool__gpa_cumulative_year`              | GPA arithmetic on stored grades | unchanged                       |
| `rpt_deanslist__transcript_gpas`                    | GPA arithmetic                  | unchanged                       |
| `rpt_deanslist__transcript_grades`                  | row population                  | repoint 4                       |
| `rpt_tableau__hs_early_warning_dashboard`           | row population                  | repoint 3                       |
| `rpt_tableau__gradebook_audit`                      | audit scope                     | unchanged, non-goal             |
| `int_extracts__gradebook_audit_student_flags`       | audit scope                     | unchanged, non-goal             |

### Models that carry it as a column without filtering

No change required, but each is a place a consumer could be relying on the old
meaning:

`fct_grades_term`, as `is_excluded_from_gpa`;
`rpt_tableau__gradebook_dashboard`; `rpt_tableau__student_course_grades`;
`rpt_tableau__gradebook_gpa`; `rpt_tableau__gradebook_es_comments`;
`rpt_tableau__gradebook_ms_hs_comments`; `rpt_tableau__gradebook_audit`;
`int_tableau__gradebook_audit_flags`;
`int_tableau__gradebook_audit_student_scaffold`;
`int_tableau__gradebook_audit_teacher_scaffold`;
`int_tableau__gradebook_audit_categories_teacher`;
`int_extracts__course_schedule_by_term`;
`int_extracts__course_enrollments_by_term`.

### The raw-column path

Six models read `courses_excludefromgpa` **directly** off
`base_powerschool__course_enrollments` or `base_powerschool__sections`, not
`exclude_from_gpa` off `base_powerschool__final_grades`. `is_graded_course` is
defined only on `base_powerschool__final_grades`, so it reaches none of them.

| Model                                           | Line     | Source                                 | Filters?     |
| ----------------------------------------------- | -------- | -------------------------------------- | ------------ |
| `int_extracts__course_enrollments_by_term`      | 73       | `base_powerschool__course_enrollments` | carries only |
| `int_extracts__course_schedule_by_term`         | 74       | `base_powerschool__sections`           | carries only |
| `int_tableau__gradebook_audit_student_scaffold` | 119, 335 | `base_powerschool__course_enrollments` | carries only |
| `int_tableau__gradebook_audit_teacher_scaffold` | 17       | `base_powerschool__sections`           | carries only |
| `rpt_tableau__gradebook_gpa`                    | 153      | `base_powerschool__course_enrollments` | carries only |
| `rpt_tableau__student_course_grades`            | 378      | `base_powerschool__course_enrollments` | carries only |

None of them filters, so none breaks. Two implications matter.

**The first 2 are one hop from being filters.** They are the join-key source for
the audit filters: `rpt_tableau__gradebook_audit.sql:96` reads
`int_extracts__course_schedule_by_term`, and
`int_extracts__gradebook_audit_student_flags.sql:105` reads
`int_extracts__course_enrollments_by_term`. They are not inert passthroughs, and
if pass/fail should ever enter the audit, `is_pass_fail` has to reach them
first. It does not today.

**`rpt_tableau__gradebook_gpa` does its real container filtering with a
hardcoded course-number list** at lines 176-186: `LOG100`, `LOG1010`, `LOG11`,
`LOG12`, `LOG20`, `LOG22999XL`, `LOG300`, `LOG9`, `SEM22106G1`, `SEM22106S1`.
That is a third independent mechanism for "not a real class," alongside
`excludefromgpa` and the grade scale. A new pass/fail course is not on the list,
so it appears, which is what we want. But the list needs maintaining for every
new container course, and this spec does not change that.

### One goal is already met by a path this spec does not touch

`rpt_deanslist__transcript_grades` has 2 branches. Repoint 4 changes the
current-year branch. The other branch, at lines 1-27, reads
`stg_powerschool__storedgrades` gated on
`ifnull(sg.excludefromtranscripts, 0) = 0` at line 27, not on `excludefromgpa`.
So once a pass/fail grade stores, it reaches the transcript with no change at
all. Goal 1 is satisfied by that branch; repoint 4 only covers the pre-store
window, when the grade is still live in the gradebook.

### Indirect consumers through the GPA models

`int_powerschool__gpa_term` feeds `fct_grades_gpa`,
`int_gpa__goal_student_metrics`, `int_powerschool__gpa_term_current`,
`int_powerschool__gpa_term_lookback`, `rpt_tableau__gpa_analysis`,
`rpt_tableau__gpa_cumulative_year`, `rpt_tableau__mtss_rti`,
`rpt_tableau__okrts_referrals`, `rpt_gsheets__gpa_roster`,
`rpt_gsheets__mtss_rti`, `rpt_gsheets__kippfwd_miami_roster`,
`rpt_deanslist__designations`, `rpt_deanslist__promo_status`, and
`rpt_deanslist__student_misc`.

`int_powerschool__gpa_cumulative` feeds `int_reporting__promotional_status`,
`int_extracts__student_enrollments`, `rpt_gsheets__gpa_flags_report`, and is
snapshotted in `kipptaf/snapshots/powerschool.yml`. A logic change writes new
snapshot history rather than restating old rows.

## Verification

Aggregate sums are not acceptable proof. Opposing student-level moves cancel to
zero. Every check below is a student-level diff against production.

### Commit 1 gate: exactly 0 differing rows

```sql
select count(*) as n_differing_rows
from {pr_schema}.int_powerschool__gpa_term as new
full outer join {prod_schema}.int_powerschool__gpa_term as old
    using (_dbt_source_relation, studentid, schoolid, yearid, term_name)
where
    new.studentid is null
    or old.studentid is null
    or abs(coalesce(new.gpa_term, -99) - coalesce(old.gpa_term, -99)) > 0.005
    or abs(coalesce(new.gpa_y1, -99) - coalesce(old.gpa_y1, -99)) > 0.005
    or abs(
        coalesce(new.gpa_y1_unweighted, -99)
        - coalesce(old.gpa_y1_unweighted, -99)
    )
    > 0.005
    or abs(coalesce(new.gpa_semester, -99) - coalesce(old.gpa_semester, -99))
    > 0.005
    or coalesce(new.n_failing_y1, -99) != coalesce(old.n_failing_y1, -99)
```

Run the same shape against `int_powerschool__gpa_cumulative` over
`cumulative_y1_gpa`, `cumulative_y1_gpa_unweighted`,
`cumulative_y1_gpa_projected`, `cumulative_y1_gpa_projected_unweighted`,
`cumulative_y1_gpa_projected_s1`, `cumulative_y1_gpa_projected_s1_unweighted`,
`core_cumulative_y1_gpa`, `earned_credits_cum`, `earned_credits_cum_projected`,
`earned_credits_cum_projected_s1`, `potential_credits_cum`,
`gpa_needed_for_cumulative_3_0`, and `is_cumulative_3_0_attainable`.

Both must return 0. Anything above 0 means the sentinel reading is wrong and the
commit stops.

### Commit 2 expected diff, stated before running

Exactly 3 columns may move, and only for students with a pass/fail enrollment:

| Column                            | Expected direction                    |
| --------------------------------- | ------------------------------------- |
| `n_failing_y1`                    | up, when a pass/fail course is failed |
| `earned_credits_cum_projected`    | up                                    |
| `earned_credits_cum_projected_s1` | up                                    |

Every GPA column must be unchanged: term, semester, `Y1`, `Y1` unweighted,
cumulative, projected cumulative, projected semester-1, core,
`gpa_needed_for_cumulative_3_0`, and `is_cumulative_3_0_attainable`. Any GPA
movement means the CTE or union-branch isolation leaked.

**The expected count is 0 differing rows, but only after the blocking
prerequisite is done.** With Camden `HR` still on scale 346, commit 2 moves 8672
rows into 2 extracts and changes `n_failing_y1` for the 4 Camden students with a
Homeroom `F`. Run the diff after Ops moves Camden `HR` to 976, and confirm 0. A
non-zero result before that is the prerequisite reminding you, not a code bug.

Because no pass/fail course exists yet, the diff cannot prove the new logic
works. Prove that with unit tests that mock a pass/fail enrollment.

Add one more check specific to this risk: assert that no row in
`base_powerschool__final_grades` has `is_pass_fail = true` before the first
pass/fail course is created. That is the direct test of the Camden Homeroom
class of failure.

### Unit tests

**Use `format: sql` for every new and edited fixture.** The 6 existing fixtures
in `int_powerschool__gpa_cumulative.yml` are dict-format on
`ref('base_powerschool__final_grades')`, and dict fixtures introspect the
deferred relation's schema at compile time. Both commit 1's rename and commit
2's new columns are same-PR schema changes, so dict format is rejected with
`Invalid column name '<col>' in unit test fixture`. Building the upstream into a
dev schema makes the dict fixture pass LOCALLY while CI still fails. See
`src/dbt/CLAUDE.md`, _dbt unit-test fixtures_.

After the rename, run the whole directory's unit tests
(`--select "test_type:unit,<fqn.dir>"`), not just the changed model. Sibling
models mock the same `ref()` and break on the same rename.

Add these tests:

1. `int_powerschool__gpa_term`: a student with 1 A-to-F course and 1 failed
   pass/fail course. Assert `gpa_y1` reflects only the A-to-F course, and
   `n_failing_y1` equals 1.
1. `int_powerschool__gpa_cumulative`: the same student. Assert
   `earned_credits_cum_projected` includes the pass/fail credits when passed,
   and that `cumulative_y1_gpa_projected` and
   `potential_gpa_credits_cum_projected` exclude them.
1. `base_powerschool__sections`: a section with `gradescaleid = 0` inherits the
   course scale, and a section with a non-zero scale overrides it.

### Standard checks

- `dbt build --select base_powerschool__sections+` in one district, then
  `kipptaf`.
- `trunk check --force` on every changed file, run from inside the worktree.
  Markdownlint fires only at pre-push and CI, so check this spec too.
- After dbt Cloud CI passes, fetch warnings with `warning_only=true` before
  declaring done.

## Open items

1. **Tableau workbooks.** About 13 `rpt_*` and `int_tableau__*` models expose
   the flag as a dimension. Whether any workbook filters or calculates on it is
   unverified, and a workbook that does would need editing. This needs a
   dashboard owner to confirm, or a query against the Tableau metadata API.
1. **Paterson grade scale.** Someone must create a scale named `Pass Fail Scale`
   in the Paterson PowerSchool instance before any pass/fail course is set up
   there. Without it `is_pass_fail` is always `false` and Paterson pass/fail
   courses silently behave like today.
1. **The reconciles-stored test.** A pass/fail-only student creates a new
   `int_powerschool__gpa_cumulative` row with a null projected GPA, which fails
   `test_int_powerschool__gpa_cumulative_year__reconciles_stored`. Guard the
   test or suppress the row. Decide before implementing.
1. **Prior-year pass/fail failures.** Counting them requires a second
   `is_pass_fail` derivation from `storedgrades.gradescale_name`. Confirm that
   prior-year failure counts are actually wanted; if only the current year
   matters, the second derivation can be dropped and the scope shrinks.
1. **The 54 Paterson divergent sections** in `terms_yearid` 34 and 35. Clean
   them in PowerSchool, or accept them as historical. They do not affect the
   current year.
1. **Column name.** `is_graded_course` versus `is_academic_course`. Not
   blocking.

## Risks

- **Section-level override widens the GPA surface.** Once a section carries its
  own scale, GPA moves for those students. That is intended, but it will not
  happen on the commit that ships it, so the warn test is the only signal. If
  the test is ignored, a GPA shift could land unnoticed.
- **The rename is NOT protected by contracts.** `powerschool/dbt_project.yml`
  enforces `contract` only under `sis: staging:`, and none of the 4 base
  `properties/*.yml` files declares one. A missed rename in those files fails
  nothing. It leaves a stale doc entry describing a column that no longer
  exists, silently. Only `fct_grades_term` is contract-enforced, through
  `kipptaf/dbt_project.yml:212-215`. Verify the base yml renames by grep, not by
  trusting the build.
- **The snapshots do not record what you would expect.**
  `snapshot_powerschool__gpa_cumulative` uses `strategy: check` with
  `check_cols` = `cumulative_y1_gpa`, `cumulative_y1_gpa_unweighted`,
  `cumulative_y1_gpa_projected`, `cumulative_y1_gpa_projected_s1_unweighted`.
  `earned_credits_cum_projected` and `earned_credits_cum_projected_s1` are NOT
  check_cols, so a change to them writes **no new snapshot row** and is
  invisible in snapshot history. `n_failing_y1` is not in that snapshot at all:
  it is a check_col on `snapshot_powerschool__gpa_term`, over
  `int_powerschool__gpa_term_current`, so a change there DOES write history and
  propagates into `int_powerschool__gpa_term_lookback`'s
  `n_failing_y1_1/2/4_week_prior`.
- **Two extracts have no tests at all.** Neither
  `rpt_deanslist__transcript_grades.yml` nor
  `rpt_tableau__hs_early_warning_dashboard.yml` declares any `data_tests`, and
  `int_powerschool__gpa_term.yml` has none either, contrary to the
  uniqueness-test rule in `src/dbt/CLAUDE.md`. The repoints land in the least
  protected part of the lineage. The verification diffs are the only safety net,
  which is why they are student-level rather than aggregate.
