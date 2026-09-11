# Move the PowerSchool section-teacher join into the package

Refs #5260. Refs #5228. Refs #5012.

Covers rows 3 and 4 of the #5260 table: `bridge_course_section_teachers` and
`rpt_clever__sections`, which each rebuild the same PowerSchool-internal
section-teacher join in kipptaf.

## Decision

Build one new package model, `int_powerschool__section_teachers`, carrying every
PowerSchool-internal join behind the section-teacher relationship. Both kipptaf
consumers read it through a `union_relations` wrapper. Restore the Miami archive
rows that PR #5259 dropped from the bridge.

Two things in #5260's table are wrong and this spec supersedes them.

**"`base_powerschool__sections` already joins teachers; add role if needed" is
not possible.** PowerSchool records a section's teachers two different ways.
`sections.teacher` is a single column on the section row — one teacher, no role,
no dates — and the package `base_powerschool__sections` already resolves it to
`teachernumber` and `teacher_lastfirst`. `sectionteacher` is a separate table
with N rows per section, each carrying `roleid` (resolving through `roledef` to
Lead Teacher, Co-teacher, Gradebook Access, Blended Learning) plus `start_date`
and `end_date`. They are different tables, not a superset. Adding role to
`base_powerschool__sections` would change its grain from one row per section to
one row per section by teacher by role, and three models read it:
`dim_course_sections`, `rpt_clever__sections`, and
`rpt_branchingminds__course_info`. All three would silently fan out.

**The acceptance criterion "the kipptaf reader is a `union_relations` wrapper or
a consumer of one" cannot be fully met here.** `int_people__staff_roster` is a
kipptaf model spanning every region and both SIS systems, and the bridge's
`staff_key` hashes `sr.employee_number`, which exists nowhere in the PowerSchool
package. The package model therefore stops at `teachernumber`; kipptaf keeps the
roster join and the hashing. That is the correct boundary — everything genuinely
internal to PowerSchool moves down, and nothing else does.

## The regression this also fixes

PR #5259 dropped `kippmiami` from `stg_powerschool__sectionteacher`,
`stg_powerschool__roledef`, and `int_powerschool__teachers`. All three feed the
bridge's PowerSchool branch, so Miami archive rows stopped resolving on
2026-09-10. The bridge was not among that PR's 43 changed files and was not in
its verification set, and its "Accepted loss" section names only the calendar
history.

Counted against `kippmiami_powerschool` on 2026-09-11:

| Role                    | Rows       | Survive the staff-roster join |
| ----------------------- | ---------- | ----------------------------- |
| Gradebook Access (edit) | 13,974     | 13,973                        |
| Lead Teacher            | 3,432      | 3,432                         |
| Co-teacher              | 1,928      | 1,927                         |
| Blended Learning        | 185        | 185                           |
| **Total**               | **19,519** | **19,517**                    |

3,423 sections, 387 teachers, AY2018 through AY2025.

Those 3,423 sit inside the 3,433 Miami history sections PR #5259 cites, which it
kept deliberately because dropping them would orphan every Miami grade and
attendance row from its section. The 10-section gap traces to a single teacher,
across 2 schools, who has no `int_powerschool__teachers` record at the school
each of those sections belongs to — verified against the archive, all 10.
`dim_course_sections` still carries all 3,433. So Miami history sections
currently exist with zero teacher rows against them, while
`bridge_course_section_teachers.yml` still documents the full role set as
present.

Nothing reads the bridge yet — its only consumer is the Cube exposure, and
`src/cube/` holds just a comment about a future bridge cube — so this is a
correctness question, not an outage. Restoring the rows keeps the bridge
consistent with the sections the same archive decision preserved.

## The package model

`src/dbt/powerschool/models/sis/intermediate/int_powerschool__section_teachers.sql`

```sql
select
    sec.sections_dcid,
    sec.sections_id,
    sec.sections_schoolid,

    st.id as sectionteacher_id,
    st.teacherid,

    t.teachernumber,

    r.name as `role`,
    r.sortorder as role_sortorder,

    cast(st.start_date as date) as effective_start_date,
    cast(st.end_date as date) as effective_end_date,
from {{ ref("base_powerschool__sections") }} as sec
inner join
    {{ ref("stg_powerschool__sectionteacher") }} as st
    on sec.sections_id = st.sectionid
inner join
    {{ ref("int_powerschool__teachers") }} as t
    on st.teacherid = t.id
    and sec.sections_schoolid = t.schoolid
inner join {{ ref("stg_powerschool__roledef") }} as r on st.roleid = r.id
```

Grain is one row per `sectionteacher` row that resolves to a section, a teacher
and a role. Uniqueness test on `sectionteacher_id`. `role` is a BigQuery
reserved word, so it takes backticks in the SQL and `quote: true` in the
properties yml.

### Sections come from `base_powerschool__sections`

Both consumers already reach sections that way — the bridge directly, and
`rpt_clever__sections` through `int_students__course_sections` to
`int_powerschool__sections_union`. `base_powerschool__sections` inner-joins
courses, terms and schools, so it is narrower than `stg_powerschool__sections`.

Measured on Newark: sourcing from staging yields 52,540 rows against 51,945 from
`base_`, a difference of 595 rows on 506 sections. Every one of those 506 drops
for a missing course, none for a term or a school, and all fall in AY2004
through AY2015 carrying retired mixed-case course numbers — `Span300`, `Sci200`,
`Tec101`, `AGRI`. `dim_course_sections` excludes them for the same reason, so
sourcing from staging would emit 595 orphan `course_section_key` values against
the bridge's `relationships` test while adding no usable history.

`base_powerschool__sections` uses `dbt_utils.star()`, which resolves its columns
from BigQuery at run time, so the 3 columns read from it are enumerated
explicitly rather than starred.

Both staging variants expose the same columns and types, so the model builds
under `dlt` (the three NJ districts) and under `odbc` (the Miami archive
rebuild) without branching. `start_date` and `end_date` are `TIMESTAMP` in all
five datasets, so the single `cast(... as date)` normalizes the union.

The archive's `stg_powerschool__sections` is already bounded at AY2025 by the
existing rebuild post-hooks, so the new model inherits the bound with no new
post-hook. Verified: `max(terms_academic_year)` is 2025.

## The kipptaf wrapper

`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__section_teachers.sql`
— standard `union_relations` plus `extract_source_project()`, matching the
sibling wrappers in that directory.

`union_relations` resolves its column list at compile time from each relation's
`INFORMATION_SCHEMA`, so it cannot name the Miami relation until the archive has
built it. That constraint sets the PR split below: the wrapper unions the three
NJ regions in PR 1 and gains Miami in PR 2.

## Consumer swaps

### `bridge_course_section_teachers`

`powerschool_teachers` goes from four joins to one:

```sql
from {{ ref("int_powerschool__section_teachers") }} as pst
inner join
    {{ ref("int_people__staff_roster") }} as sr
    on pst.teachernumber = sr.powerschool_teacher_number
```

Hash inputs stay `sections_dcid` and `_dbt_source_project`, so
`course_section_key` does not churn — `int_students__course_sections` derives
`sections_dcid` from the same `stg_powerschool__sections.dcid` the package model
reads. The Focus branch is untouched.

The two branches stay disjoint with no new filter. The PowerSchool branch
carries Miami AY2018 through AY2025 (the archive bound); the Focus branch
carries AY2026 forward via its existing
`terms_academic_year >= min_academic_year` guard.

### `rpt_clever__sections`

`teachers_long` keeps `int_students__course_sections` for its section, course,
and term attributes, and replaces its three teacher joins with one:

```sql
inner join
    {{ ref("int_powerschool__section_teachers") }} as pst
    on sec.sections_id = pst.sections_id
    and sec._dbt_source_project = pst._dbt_source_project
```

reading `pst.role_sortorder as sortorder` and `pst.teachernumber`. The
`sec.sections_schoolid = t.schoolid` predicate it drops is now inside the
package model as `sec.schoolid = t.schoolid`. The model's existing
`!= 'kippmiami'` filter stays — Clever does not serve Miami.

## PR 1: package model, NJ wrapper, both consumers

- Add the package model and its properties yml.
- Re-include the `powerschool` package in `kippmiami` per the recipe in
  `src/dbt/kippmiami/CLAUDE.md`, so the archive can build the new model.
- Add the kipptaf wrapper unioning Newark, Camden, and Paterson.
- Add the source entry to `sources-kippnewark.yml`, `sources-kippcamden.yml`,
  and `sources-kipppaterson.yml`.
- Swap both consumers.

CI needs a `--target staging` seed of the new model in the three NJ districts,
because a new package model has no `zz_stg_*` copy and kipptaf CI cannot
otherwise resolve the source. That writes shared staging tables and needs direct
user authorization.

After merge, the archive model is materialized into `kippmiami_powerschool`.

## PR 2: Miami

- Remove the `powerschool` package from `kippmiami` again, per the same recipe.
- Add Miami as the fourth relation in the kipptaf wrapper.
- Add the source entry to `sources-kippmiami.yml` and update its prose from 11
  permanent tables to 12.

The bridge is NJ-only between the two merges, then the Miami rows land. No build
ever references a relation that does not exist.

## Verification

- `rpt_clever__sections` row-identical to prod after PR 1. The Clever feeds were
  verified byte-for-byte in PR #5259, so any delta is this change.
- `bridge_course_section_teachers` row-identical to prod for NJ after PR 1.
- After PR 2, the bridge gains approximately 19,517 Miami rows across 3,423
  sections and 4 roles, and `course_section_key` values are unchanged on every
  pre-existing row.
- `dim_course_sections` unchanged at its current row count, with no new orphan
  `course_section_key` in the bridge's `relationships` test.
- The new package model passes its uniqueness test in all four districts.

## Documentation

`bridge_course_section_teachers.yml` lines 17 and 18 claim Miami archive years
flow through the PowerSchool branch with their full role set. That is false on
`main` today and true again after PR 2, so the text stands as written and needs
no edit. The `source_model` pointers on `role`, `effective_start_date`, and
`effective_end_date` change from `stg_powerschool__roledef` and
`stg_powerschool__sectionteacher` to `int_powerschool__section_teachers`.

## Not in scope

- The other four rows of #5260. Rows 1, 2, 5, and 6 stay open on that issue.
- The `base_powerschool__*` compatibility passthroughs. `rpt_clever__sections`
  already reads `int_students__course_sections` directly; the bridge keeps
  reading the passthrough for its Focus branch. The full wrapper sweep stays on
  #3999.
- `int_powerschool__gradebook_assignments_scores`, whose move is blocked on
  deciding what happens to its `extract_region()` call, a kipptaf-only macro
  over `_dbt_source_project`.
