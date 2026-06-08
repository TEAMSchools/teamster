# Design: make `fct_assessment_scores_enrollment_scoped` truly enrollment-scoped

- **Issue:** [#4135](https://github.com/TEAMSchools/teamster/issues/4135)
- **Date:** 2026-06-05
- **Type:** refactor (dbt)

## Problem

`fct_assessment_scores_enrollment_scoped` carries two FK routes to
`dim_students`:

1. Direct: `student_key` → `dim_students`
2. Chain: `student_section_enrollment_key` → `dim_student_section_enrollments` →
   `dim_student_enrollments` → `dim_students`

This is a diamond path, which the marts strict-chain convention prohibits
(`src/dbt/kipptaf/models/marts/CLAUDE.md` → "Strict-chain traversal").

The direct `student_key` exists today only because the section-enrollment chain
is **non-total**: `student_section_enrollment_key` is null for all state
assessments and for unresolved internal rows, so the chain cannot reach the
student for those rows. The fact mixes two implicit scopes (section-resolved
internal interims; student-only state tests) behind one grain.

## Goal

Make the fact live up to its name: every retained row resolves to a section
enrollment, so the student is reached through a single chain. Eliminate the
direct `student_key` FK and the diamond, without losing student attribution.

## Profiling (prod, 14,210,311 rows)

| Tier                                     | Rows       | %     |
| ---------------------------------------- | ---------- | ----- |
| Truly unattributable (no student at all) | 39         | 0.0%  |
| Known student, no section (today)        | 604,662    | 4.3%  |
| Already section-resolved                 | 13,605,610 | 95.7% |

The "known student, no section" tier breaks down as **505,143 internal / 9,577
students**, **77,626 state / 13,491 students**, 21,893 other. The unresolved
population is mostly _internal_ resolution gaps (replacement curriculum, ES
Writing, advanced-math carve-out, enrollment non-overlap), not state — so a
fallback tier does the heavy lifting and the state crosswalk is precision on
top.

Homeroom coverage: **99% of student-years (71,099 / 71,799 since AY2018) have an
`HR` enrollment.** The 1% gap is dominated by Paterson AY2024–25 (the newest
region, 463 of ~700 student-years); the remainder is scattered single/double
digits. Homeroom is a real course-enrollment (`cc`) row
(`courses_credittype in ('HR', 'Homeroom')`), so it produces a valid
`student_section_enrollment_key`.

## Decisions

1. **Single fact.** The only rows an enrollment-scoped fact loses are the 39
   truly unattributable scores. There is no orphan-score population worth a
   parallel student-scoped fact. The 604K "no section" rows are not lost — they
   resolve to a section under the new resolver and stay in the fact.
2. **Grain = section enrollment (Approach A).** The fact keeps
   `student_section_enrollment_key` as its single enrollment FK. Rejected
   alternatives: stint grain (`student_enrollment_key`) discards section-level
   analysis, which is the model's primary use case; a score→section bridge is
   wrong because the relationship is M:1 (the resolver dedups to one section per
   score) and a bridge would relocate the diamond onto the bridge node (two
   paths to `dim_students`), which the same no-diamond rule prohibits.
3. **Resolver stays an intermediate.**
   `int_assessments__resolved_section_enrollments` remains an `int_` model (not
   folded into the fact, not promoted to marts). Rationale: it keeps an
   independent uniqueness-test seam that catches resolver fan-out before it
   corrupts the fact PK; it keeps the fact thin; and it is the natural
   consolidation point for internal + state + homeroom resolution.
4. **Resolution is total by construction.** Rows that resolve to no section
   (subject nor homeroom) are excluded from the fact via INNER join — they join
   the 39 as an upstream match-rate concern, not a mart row.

## Components

### 1. `int_assessments__resolved_section_enrollments` (expanded)

Becomes the single resolver for **all** scores (internal + state). Today it
filters `is_internal_assessment`; that filter is removed and a state branch is
added. Each score resolves to one section via an ordered tier cascade; the first
tier that hits wins and stamps `resolution_type`.

**Enrollment source — read the inventory directly.** The resolver stops sourcing
its enrollments from `int_assessments__scaffold` and instead joins
`int_assessments__course_enrollments` directly. The two assessment models are
**inventory vs. selection**, not duplicates:
`int_assessments__course_enrollments` is the enrollment inventory (one row per
student course enrollment, carrying `cc_dcid`, `courses_credittype`,
`illuminate_subject_area`, dates, region, and the illuminate year/grade offsets
— including 88,467 `HR` rows, all with `cc_dcid`); the resolver is the selection
(pick the one enrollment active at test time). Today resolution is routed
through the scaffold, which has already inner-joined the inventory by
`subject_area + administered_at` (and excluded advanced-math) — duplicating the
subject+date matching, and, fatally, **internal-only**: the scaffold's state
branches carry `cc_dcid = null`, so it can never yield a state→section mapping.
Reading the inventory directly (a) unifies internal + state against one source,
(b) removes the duplicated matching, and (c) gets the `HR` tier for free since
the inventory already carries it. The scaffold is unchanged and keeps its own
job (building the assessment×student grid for `response_rollup`); it is simply
no longer the resolver's enrollment source.

| Tier | `resolution_type` | How                                                                                                                                                                               |
| ---- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | `subject_section` | Subject-matching course section active on the anchor date. Internal: existing `illuminate_subject_area` logic. State: new state-subject → course-subject crosswalk (Component 2). |
| 2    | `homeroom`        | The student's `HR` section for the academic year (`courses_credittype = 'HR'`).                                                                                                   |
| —    | _(none)_          | No subject section and no homeroom → row excluded from the fact.                                                                                                                  |

There is no `other_enrollment` / any-section tier (explicitly dropped). Output
grain and uniqueness test cover internal and state keys; the resolver dedups to
one section per score (M:1).

**Selection rule: the section active on the assessment date wins.** Both
branches resolve by picking the subject-matching enrollment whose
`[entry_date, exit_date)` window contains an anchor date — this is the
deterministic tiebreaker for mid-year section switches.

- **Internal:** the anchor is the sitting date (`date_taken`), falling back to
  the scheduled administration date — as today.
- **State:** a **real per-student test date** is available in source and must be
  threaded through (Component 3); the state branch anchors on it, same
  window-containment pick as internal. No season proxy.

Academic year still scopes the candidate set, so the state branch reconciles the
inventory's illuminate `+1` offset
(`illuminate_academic_year = cc_academic_year + 1`) against the state score's
`academic_year` (match on raw `cc_academic_year`) before the date-containment
pick.

### 2. State subject crosswalk (Component for Tier 1, state)

State resolution needs to map
`(state subject_area / discipline) → course subject` so the resolver knows which
section type to look for: NJSLA ELA → ELA, NJSLA Math → Math, NJSLA Science →
Science, NJGPA → ELA / Math, FAST → ELA / Math.

**Start with an inline `CASE`.** Derive the mapping as a named column (e.g.
`state_course_subject`) in a CTE inside the resolver — the state subject set is
small and stable, and an inline `CASE` avoids a new external dependency for the
first cut. (This is a plain derived column, not a `generate_surrogate_key`
input, so the CLAUDE.md "no inline CASE in surrogate keys" rule does not apply.)
Graduate to a dbt seed or a `course_subject_crosswalk` sheet tab later if Ops
needs to edit the mapping without a code change. State subjects with no clean
course mapping fall through to Tier 2 (homeroom).

### 3. State test date — thread it through (do not bypass the intermediates)

A real per-student test date exists in the raw state sources and is dropped at
the staging projection:

- **Pearson (NJ):** `src_pearson__{parcc,njsla,njsla_science,njgpa}` carry
  `unit{1..4}onlineteststartdatetime` / `...enddatetime` and
  `paperattemptcreatedate` / `attemptcreatedate`. Derive one `test_date` (e.g.
  earliest online unit start, coalesced with the paper attempt date) in the
  `stg_pearson__*` models, which currently omit them.
- **FLDOE (FL):** `src_fldoe__{fast,eoc,science}` carry `date_taken` and
  `test_completion_date`; `stg_fldoe__fast` already casts `date_taken` to
  `DATE`. Carry `date_taken` through (cast the `eoc` / `science` string
  versions).

Thread that `test_date` up through `int_pearson__all_assessments` and
`int_fldoe__all_assessments` (additive column) so the fact and resolver get a
real date. **We keep sourcing the `int_*__all_assessments` models** — they do
the multi-test-type union + crosswalk + standardization the fact needs;
bypassing them to read staging directly would duplicate that. The fix is to stop
the intermediates from dropping the date, not to route around them. These are
kipptaf-level staging/intermediate models reading raw district sources that
already contain the columns, so the change is single-PR and additive.

### 4. `fct_assessment_scores_enrollment_scoped` (the fact)

- INNER joins the expanded resolver (unresolved rows drop → totality by
  construction).
- Drops `student_key` and the entire state-branch `dim_students` join.
- State `test_date_key` is now populated with the real threaded test date (today
  the state branch sets it `null`) — the `dim_dates` FK becomes meaningful for
  state rows, a bonus fix.
- Adds `enrollment_resolution` as a degenerate dimension (the `resolution_type`
  above) so course-level rollups can filter to `subject_section` and exclude
  coarse `homeroom` rows.
- Stays thin: union the internal + state score rows → one INNER join to the
  resolver → project columns. All section-resolution complexity lives in the
  resolver.

Result: single FK to `dim_student_section_enrollments`, single chain to
`dim_students`, diamond eliminated.

### 5. YAML / contract / exposure

- Remove the `student_key` column block (description, FK constraint,
  `relationships` test) from
  `marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`.
- Add the `enrollment_resolution` column (degenerate dim; `accepted_values`
  test: `subject_section`, `homeroom`).
- Tighten `student_section_enrollment_key` description (now populated for every
  row; document the tier semantics and that `homeroom` rows are coarse).
- Update the resolver's properties YAML: drop the internal-only language, add
  the state branch description, keep/tighten the uniqueness test.
- Confirm the Cube exposure in `models/exposures/cube.yml` still validates;
  `src/cube/model/` does not currently read `student_key`, so no Cube model
  change is expected — verify by grep before merge.

## Hash-change discipline

`assessment_score_key` (the PK) is hashed from score-grain inputs
(`student_number` + assessment identifiers), **not** from the FKs — so dropping
`student_key` and adding rows via state resolution does **not** change the PK
hash. `student_section_enrollment_key` is computed by the resolver
(`surrogate_key(cc_dcid, _dbt_source_project)`); its value set changes for
previously-unresolved rows (null → a real key), which is expected and is the
point of the change. No consumer hashes `student_key`, so its removal is a
column drop, not a hash migration.

## Testing

- Resolver: uniqueness on its output grain (one section per score) — the primary
  fan-out guard.
- Fact: existing `assessment_score_key` `unique` + `not_null`; `relationships`
  on `student_section_enrollment_key` → `dim_student_section_enrollments` (now
  expected ~100% populated); `accepted_values` on `enrollment_resolution`.
- Post-build validation in the PR-branch schema: confirm
  `student_section_enrollment_key` is ~100% non-null and the fact row count
  equals prior `n_resolved + n_student_no_section` minus the unresolved residual
  (the 39 + no-homeroom tail), per `marts/CLAUDE.md` "Verify FK population".
- Build:
  `uv run dbt build --select int_assessments__resolved_section_enrollments+ fct_assessment_scores_enrollment_scoped+`
  against kipptaf.

## Out of scope / follow-ups

- **The 39 truly-unattributable scores** (state rows that do not match a student
  in `dim_students`) get a separate follow-up issue to investigate the identity
  match, not addressed here.
- **No-homeroom residual** (mostly Paterson AY2024–25): these rows drop from the
  fact. Surfaced via the resolver match-rate, tracked with the 39-row follow-up
  rather than papered over with an `other_enrollment` tier.
- **State crosswalk gaps** (subjects with no clean course): resolve to homeroom
  by design; revisit only if a precise-section need emerges.

## Risks

- Mid-year section switches are resolved deterministically by date-window
  containment (the section active on the assessment date wins), using a real
  test date for both internal and state. Pearson tests span multiple online
  units across days, so the derived `test_date` must pick a deterministic unit
  (e.g. earliest unit start); a switch landing mid-test could attribute to the
  section active at the chosen unit. Acceptable; the `enrollment_resolution`
  flag does not distinguish this from a clean pick.
- Threading `test_date` touches `stg_pearson__*` and the
  `int_*__all_assessments` models (additive). Verify no other consumer breaks on
  the added column, and that `test_date` parses cleanly — the raw Pearson
  datetimes are `STRING`.
- Expanding the resolver to all scores increases its build cost; the fact's
  INNER join replaces a LEFT join, so verify no unexpected row loss beyond the
  documented residual.
