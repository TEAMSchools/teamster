# Move the PowerSchool gradebook assignment-score join into the package

Refs #5260. Refs #5228. Refs #5012.

Covers rows 5 and 6 of the #5260 table. Row 5 moves
`int_powerschool__gradebook_assignments_scores` into the `powerschool` package
behind a kipptaf `union_relations` wrapper. Row 6 needs no code change; the
reason is recorded below.

Follows the pattern set by
`docs/superpowers/specs/2026-09-11-powerschool-section-teachers-design.md`: one
package model carrying every PowerSchool-internal join, a kipptaf wrapper above
it, and the kipptaf-only concerns left in kipptaf.

## Decision

Move the model to
`src/dbt/powerschool/models/sis/intermediate/int_powerschool__gradebook_assignments_scores.sql`
unchanged except for five deletions, and replace the kipptaf model with a bare
`union_relations` wrapper over the three NJ regions. Drop the `region` and
`credit_type` columns. One PR. No Miami, no archive rebuild.

Three things in #5260's table are wrong and this spec supersedes them.

### The blocker is not `extract_region`, and the model does not "qualify as-is"

#5260's "For Claude" note says `int_powerschool__gradebook_assignments_scores`
"qualifies as-is", and the 2026-09-11 comment on that issue says the only
obstacle is its `{{ extract_region("a") }} as region` call. Both understate it.

The model refs `base_powerschool__course_enrollments`. In kipptaf that name
resolves to a compatibility passthrough over `int_students__course_enrollments`,
which is a cross-SIS union: it carries a Focus branch,
`int_people__staff_roster`, `stg_powerschool__s_nj_crs_x`, a Google Sheets
course-subject crosswalk, a Focus academic-year boundary, and its own
`extract_region()` call. That is not a PowerSchool package model. `ref()`
resolves to the current project's copy, so the move silently re-points this
input at the package's own `base_powerschool__course_enrollments` — a different
model with the same name.

That re-point is sound, and measured below. But it is the substance of this
change, not a detail.

### `credit_type` is the real behavior risk

`int_students__course_enrollments` conforms PowerSchool credit types to Focus's
vocabulary before kipptaf sees them:

```sql
case
    when a.courses_credittype in ('ENG', 'ELA') then 'ENG'
    when a.courses_credittype in ('MATH', 'Math') then 'MATH'
    when a.courses_credittype in ('SCI', 'Science') then 'SCI'
    when a.courses_credittype in ('HR', 'Homeroom') then 'HR'
    else a.courses_credittype
end as courses_credittype
```

The package `base_powerschool__course_enrollments` does not. Counted against
prod on 2026-09-11, the remap fires on 4,894 rows that reach this model, all
Paterson:

| Raw value  | Score rows | Academic years |
| ---------- | ---------- | -------------- |
| `ELA`      | 1,640      | 1              |
| `Math`     | 1,579      | 1              |
| `Homeroom` | 988        | 2              |
| `Science`  | 687        | 1              |
| **Total**  | **4,894**  |                |

Moving the model without accounting for this ships a silent value change on
those rows. `Language` and `ELASkill` also survive in prod `credit_type`, so the
remap is not exhaustive even today.

### Row 6 needs no code change

#5260's table pairs `rpt_tableau__gradebook_assignments` with row 5 as "the same
assignment-score join". Two reasons it is not actionable.

It is disabled. `config: enabled: false` sits at
`src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_assignments.yml`
lines 3 and 4, and was set before #5260 was filed —
`docs/superpowers/specs/2026-08-12-deanslist-missing-assignments-lineage-design.md`
already records it as "disabled, not deleted". Refactoring it changes no live
relation.

It also rebuilds a different join. Its chain is
`base_powerschool__course_enrollments` to `int_extracts__student_enrollments` to
`int_powerschool__section_grade_config` to
`int_powerschool__gradebook_assignments` to `stg_powerschool__assignmentscore`,
across two `union all` branches split on `grading_formula_weighting_type`. Two
of those inputs are kipptaf models, so the join is not PowerSchool-internal and
no single package model absorbs it.

Row 6 closes by inspection.

## Dropping `region` and `credit_type`

Both columns have the same profile: zero enabled readers, not declared in the
model's properties yml, so no test and no description to update, no `src/cube/`
reference, and no exposure. Their only readers are in the pre-AY2627
gradebook-audit cluster that `src/dbt/kipptaf/CLAUDE.md` documents as dead — the
same cluster carrying five stale `union_dataset_join_clause` calls from the
macro deleted in #3142.

| Consumer                                              | Reads `region` | Reads `credit_type` | Enabled |
| ----------------------------------------------------- | -------------- | ------------------- | ------- |
| `int_powerschool__gradebook_assignment_scores_rollup` | no             | no                  | yes     |
| `int_students__gradebook_assignments_scores`          | no             | no                  | yes     |
| `rpt_deanslist__missing_assignments`                  | no             | no                  | yes     |
| `int_tableau__gradebook_audit_assignments_student`    | no             | no                  | no      |
| `int_tableau__gradebook_audit_assignments_teacher`    | yes            | no                  | no      |
| `int_tableau__gradebook_audit_categories_teacher`     | yes            | yes                 | no      |

Verified on `main` at 8ce3f86557; all three disabled states re-confirmed in
their properties yml. `int_tableau__gradebook_audit_student_scaffold` and
`_teacher_scaffold` also carry a `credit_type`, but derive it themselves from
`ce.courses_credittype` rather than reading this model.

`region` must go: neither `extract_region` nor `_dbt_source_project` exists in
the package, and inside the package one project is one region, so there is
nothing to extract from.

`credit_type` could stay if the remap moved to the kipptaf wrapper, but it
should not. The wrapper would then carry a copy of a conform expression that
already lives in `int_students__course_enrollments`, which is exactly the
copy-paste `src/dbt/kipptaf/CLAUDE.md` warns against under _Reuse existing
entity identity_ — and the wrapper would stop being a bare union. Dropping the
column costs nothing today and removes the duplication question entirely.

If the audit cluster is ever re-enabled, both columns come back the way every
other kipptaf model gets them: `region` from `extract_region()` at the wrapper,
`credit_type` from `int_students__course_enrollments`, where the conformed value
is defined. Re-enabling those models already requires swapping the five stale
macro calls, so this is one more line in that job rather than a new problem.
Note that `int_tableau__gradebook_audit_categories_teacher` joins
`s.credit_type = e1.credit_type` against a scaffold that carries the _conformed_
value — so keeping a raw `credit_type` on the package model would make that join
silently under-match on the 4,894 rows. Dropping is safer than keeping raw.

## The package model

`src/dbt/powerschool/models/sis/intermediate/int_powerschool__gradebook_assignments_scores.sql`

The current kipptaf SQL, with five deletions and no additions:

| Deletion                                                                       | Reason                                              |
| ------------------------------------------------------------------------------ | --------------------------------------------------- |
| `a._dbt_source_project` from the `scores` and `assignment_coding` select lists | One project is one region inside the package        |
| `and a._dbt_source_project = e._dbt_source_project` on the enrollment join     | same                                                |
| `and a._dbt_source_project = s._dbt_source_project` on the score join          | same                                                |
| `{{ extract_region("a") }} as region` and `region` in `assignment_coding`      | Macro absent from the package; zero enabled readers |
| `e.courses_credittype as credit_type` and `credit_type` in `assignment_coding` | Zero enabled readers; see above                     |

Everything else survives verbatim: the half-open enrollment range
(`a.duedate >= e.cc_dateenrolled and a.duedate < e.cc_dateleft`), the
`not e.is_dropped_section` guard, the `is_expected` case, `school_level_alt`
with its hardcoded `cc_schoolid = 179905`, the six `is_expected_*` counters, and
all six `assign_*` flags.

Grain is one row per assignment per student —
`(assignmentsectionid, students_dcid)`. That takes a
`dbt_utils.unique_combination_of_columns` test, the two-column form of the
composite the kipptaf model carries today.

### The three refs resolve inside the package

`ref("int_powerschool__gradebook_assignments")`,
`ref("base_powerschool__course_enrollments")` and
`ref("stg_powerschool__assignmentscore")` each have a package copy, so the SQL
text of the `from` and `join` clauses is unchanged. Only the resolution target
moves.

### `school_level_alt` moves unchanged

The hardcoded `e.cc_schoolid = 179905` is a Camden school number —
`stg_powerschool__schools` has one matching row in `kippcamden_powerschool` and
zero in Newark and Paterson. The predicate is therefore correctly inert in the
other two districts and needs no regional branching.

### Column order is untouched

`region` sits between the three `coalesce()` calls and the `is_expected` case;
`credit_type` sits inside the `e.` plain-reference group. Removing either leaves
the surrounding order intact, so sqlfluff ST06 stays satisfied without
reordering. Do not reorder anything while making these deletions.

## The kipptaf wrapper

`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql`

A bare `union_relations` over the three NJ regions plus
`extract_source_project()`, replacing the current 200-line model. This is the
same shape as `int_powerschool__gradebook_assignments` one layer up in the same
directory — package view, kipptaf union view — which is the sibling to copy and
is already proven in prod.

The wrapper keeps the existing three-column composite uniqueness test
`(_dbt_source_project, assignmentsectionid, students_dcid)`. Removing it would
be a test removal, and `.claude/rules/dbt-models.md` requires a uniqueness test
on every intermediate.

Miami is deliberately absent, and stays absent. `kippmiami` does not consume the
`powerschool` package, and the model's own description already records it as
NJ-only by design: Miami's gradebook is in Focus, ratified on #4996, with the
Focus branch tracked as #5010. There is no archive relation to build and no
second PR.

## Consumer swaps: none

All three enabled consumers read the wrapper at the same name and read only
columns that survive:

- `int_powerschool__gradebook_assignment_scores_rollup` groups on
  `_dbt_source_project`, `sectionsdcid`, `assignmentsectionid`, `assignmentid`,
  `assignment_name`, `duedate`, `scoretype`, `totalpointvalue`, `category_code`
  and aggregates 14 flag columns.
- `int_students__gradebook_assignments_scores` selects 19 columns including
  `academic_year` and `iscountedinfinalgrade`.
- `rpt_deanslist__missing_assignments` selects 7 and filters on `academic_year`,
  `is_expected_missing`, and `school_level_alt`.

`academic_year` is read and stays. No consumer file changes.

## Verification

The old and new join forms run against PRODUCTION relations, diffed with
`EXCEPT DISTINCT` in both directions. Do not use a dev build: kipptaf `source()`
resolves to personal `zz_<user>_*` copies under `target=dev`, and
`--favor-state` governs `ref()` but not `source()`, so a new package model is
simply absent there.

- Per NJ district, the new form over prod package relations against the prod
  kipptaf model filtered to that region, over the 39 surviving columns, both
  directions empty. The model is roughly 23M rows, so chunk the comparison by
  `academic_year`.
- Row count per region matches the prod kipptaf model's count for that region.
- The package model's uniqueness test passes in all three NJ districts.
- The rollup, `int_students__gradebook_assignments_scores`, and
  `rpt_deanslist__missing_assignments` are row-identical to prod.

### Expected equivalence evidence, measured 2026-09-11

All 13 columns the model reads from `base_powerschool__course_enrollments` exist
on the package relation: `cc_academic_year`, `cc_dateenrolled`, `cc_dateleft`,
`cc_schoolid`, `courses_course_name`, `courses_credittype`,
`is_dropped_section`, `school_level`, `sections_dcid`, `sections_grade_level`,
`students_dcid`, `students_student_number`, `teacher_lastfirst`.

Row counts, package relation against the kipptaf union filtered to that region:

| Region   | Package | kipptaf | Delta |
| -------- | ------- | ------- | ----- |
| Newark   | 590,374 | 590,374 | 0     |
| Camden   | 148,369 | 148,346 | -23   |
| Paterson | 14,837  | 14,829  | -8    |

The 31-row shortfall is staleness in the kipptaf side, not a filter:
`kipptaf_powerschool.int_powerschool__course_enrollments_union` is a TABLE last
materialized at 19:05:54, while the Camden and Paterson package relations
rebuilt at 19:44:57 and 19:16:42. Newark, which had not rebuilt in between,
matches exactly.

The kipptaf chain's two LEFT JOINs (`stg_powerschool__s_nj_crs_x` on
`courses_dcid`, and the course-subject crosswalk on `cc_course_number`) do not
fan out — if they did, the kipptaf side would exceed the package side rather
than trail it.

## CI cost

A new package model has no `zz_stg_*` copy, so kipptaf CI cannot resolve the new
source until one exists. Seed it with
`dbt build --select int_powerschool__gradebook_assignments_scores --target staging`
in `kippnewark`, `kippcamden`, and `kipppaterson`, serially — parallel runs
across projects exhaust BigQuery's `INFORMATION_SCHEMA.simple_rate.user` quota.
That writes shared staging tables and needs direct user authorization.

Three source entries are added, one per NJ district source file.

## Documentation

`docs/models/gradebook-audit-data-model.md` is a published page in the
`mkdocs.yml` nav and describes this model's joins, which do not change. It
mentions `region` only as the grain of other models and never mentions
`credit_type`, so no column text goes stale. Audit its
`int_powerschool__gradebook_assignments_scores` section for any claim about
which project the model lives in, and correct only that.

## Not in scope

- Rows 1 and 2 of #5260 stay open. Row 1 (`rpt_tableau__student_course_grades`)
  is the one that table is most wrong about: `base_powerschool__final_grades`
  lacks `sections_dcid`, `section_number`, `external_expression` and
  `rn_course_number_year`, and filters to the current year while that model
  needs the prior year too. It is not the swap the table describes.
- The `base_powerschool__*` compatibility passthroughs. The full wrapper sweep
  stays on #3999.
- Re-enabling the pre-AY2627 gradebook-audit cluster, and the five stale
  `union_dataset_join_clause` calls inside it.
- Any change to `int_students__course_enrollments`, including making its
  credit-type conform exhaustive over `Language` and `ELASkill`.
