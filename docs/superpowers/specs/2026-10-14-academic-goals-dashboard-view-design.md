# Academic goals dashboard view on stored buckets — design

Refs #5890

## Context

The Academic Goal Roll-Up workbook
(`tableau.kipp.org/#/site/KIPPNJ/workbooks/8884`, luid
`15cb4859-ab6d-46a7-8e4f-1aa786785aa3`) runs on
`rpt_tableau__academic_goals_rollup`, which recomputes the whole SY26
methodology on every refresh: the bubble parameter, scale-score ranks, and a
region-specific CASE that assigns `student_tier_calculated`. Since then the
goal-setting generator (private repo `TEAMSchools/academic-goal-setting`) became
the single owner of that math. It computes school goals and student buckets per
group; the data team loads every goal number into the academic goals sheet and
uploads the buckets to PowerSchool special programs (NJ) and Focus custom
student groups (Miami). The view never caught up, and the workbook's two Miami
tabs read a hand-published extract (`miami_goals_new`) instead of the warehouse.

Decisions settled in brainstorming with the owner:

- The view calculates nothing. Goals are read from the goals sheet; buckets are
  read from what was uploaded to PowerSchool and Focus.
- The generator's school and grade goals are pasted back into the sheet
  (`School Goal`, `Grade Goal` columns), so every goal permutation the dashboard
  shows is a sheet lookup.
- Official rollup measures derive from bucket membership over the live roster.
  Score-based columns sit beside them, plainly named, for comparison only.
- Rows carry a tested flag so Tableau can swap the percentage denominator
  (enrolled vs tested) with a parameter.
- The roster follows enrollment: a student who leaves drops off on the next
  refresh; a student who arrives with no stored assignment shows as Bucket 4.
- One student-grain datasource feeds all four workbook tabs, all four regions.
  `miami_goals_new` is retired.
- Scope is `academic_year >= 2026` (SY27 onward, when the stores became
  authoritative). The old view is disabled in place as the frozen SY26 record.

## Goals

1. A new reporting view whose only logic is joins: roster x stored buckets x
   benchmark scores x sheet goals, one row per enrolled student x subject.
2. Bucket assignments decoded from the uploads themselves, so a rollout-PD
   amendment entered in PowerSchool or Focus reaches the dashboard with no
   pipeline work.
3. Layer-rule compliance with zero new baseline rows: the old view's two
   baselined A1 edges (`stg_renlearn__star`,
   `base_powerschool__course_enrollments`, #5812) are not re-created.
4. The workbook repointed to the one datasource, with an exposure.

## Non-goals

- No goal or bucket computation anywhere in dbt. If a number is wrong, it gets
  fixed in the generator or the sheet, not here.
- No prior-year backfill. SY26 stays on the disabled view's frozen relation.
- No DDI Suite tier migration. The Student Tier filter there can later read the
  same bucket intermediate; that is a follow-up issue.
- No amendment-form plumbing. Amendments land in the stores directly.

## Why two new intermediates instead of logic in the view

The dashboard view could, mechanically, decode buckets and assemble scores
inline the way the old view did. It must not, for four specific reasons:

1. **The layer rules leave no legal inline path.** An `rpt_` may read only marts
   and domain intermediates (allowed-edges table,
   `.claude/rules/dbt-architecture.md`). Every raw input here is off-limits at
   the rpt layer: `int_powerschool__spenrollments` is a _source_ intermediate,
   the Focus group tables and `stg_renlearn__star` are staging. The old view
   survives on two **baselined** A1 edges
   (`src/dbt/kipptaf/standard-baseline.tsv`, #5812); the baseline is a ratchet
   for retiring old edges, not a precedent for new ones, and `dbt-layer-check`
   fails a new model that re-creates them. #5855 moved the same class of
   shortcut (kipptaf `stg_` over district `int_`) in the same direction: unions
   and decodes belong in intermediates.
2. **Bucket decode is identity resolution with two consumers.** "Which stored
   program or group memberships put which student in which bucket" is a
   business-entity definition, and the DDI Suite's Student Tier filter needs the
   identical answer. Today the two dashboards compute tiers independently and
   drift; with `int_students__bucket_assignments` there is one home, and the DDI
   migration becomes a ref swap.
3. **The grain test is the upload quality gate.** A student uploaded into two
   bucket programs for one subject is detectable only at student x year x
   subject grain, _before_ the roster join fans it out. A uniqueness test on an
   intermediate fails loudly at the right place; the same mistake inside a wide
   rpt would surface as a duplicated dashboard row with no pointer to the cause.
4. **The score panel is comparison infrastructure, not view logic.** The
   benchmark columns re-create exactly the Star staging read the baseline
   exempts only for the old view. Relocated to
   `int_assessments__goal_benchmarks`, the panel is legal, testable at its own
   grain, and reusable by the DDI Suite and any future goal-adjacent view
   instead of being rebuilt per dashboard.

What this deliberately does not do: no marts (none covers these entities; the A2
missing-mart issue is filed at PR time, and marts remain the fuller future
answer), and no third intermediate for course sections (that join extends the
existing roster intermediate instead).

## Components

### 1. Focus custom-group sources in kipptaf

Add `student_groups` and `students_join_groups` to
`src/dbt/kipptaf/models/focus/sources-kippmiami.yml` with passthrough wrappers
`stg_focus__student_groups` and `stg_focus__students_join_groups` in
`src/dbt/kipptaf/models/focus/staging/`, following the existing wrappers in that
folder. These wrap district **staging** relations, which the #5855 rule still
allows (the ban is on wrapping a district `int_`/`base_`). Single-region source,
so plain `select *,` passthroughs, no union, no uniqueness tests (the package
models hold them), no contract.

### 2. `int_students__bucket_assignments` (new domain intermediate)

`src/dbt/kipptaf/models/students/`. Grain: one row per `student_number` x
`academic_year` x `subject` (Math/Reading), enforced with a uniqueness test at
`severity: error` — a student sitting in two bucket programs for one subject is
an upload mistake this model must surface, not mask.

Two branches, unioned:

- **PowerSchool** (Newark, Camden, Paterson): `int_powerschool__spenrollments`
  filtered to `specprog_name like 'Bucket%'`. Bucket and subject decode from the
  program name itself (`Bucket 1 - ELA`, `Bucket 2 - Math`): regexp the bucket
  label, map `ELA` to Reading. Region comes from `_dbt_source_relation`.
  Academic year scoping comes from the enrollment's entry/exit dates
  (implementation verifies whether `spenrollments` carries a usable year key
  directly; otherwise map `enter_date` into the academic-year window). No
  dependency on the generator's `ps_programs.yaml` crosswalk — the names are the
  contract, and the generator's `verify-crosswalk` command already polices them
  against the same relation.
- **Focus** (Miami): `stg_focus__students_join_groups` joined to
  `stg_focus__student_groups` filtered to `title like 'Bucket%'`, same
  bucket/subject decode from the title. Focus student ids resolve to
  `student_number` through the existing kipptaf `stg_focus__students` wrapper.

Columns: `student_number`, `academic_year`, `region`, `subject`, `bucket`
(string, `Bucket 1`..`Bucket 3`; Bucket 4 is never stored — it is the
everyone-else default applied downstream), `bucket_store` (`powerschool` /
`focus`).

### 3. Benchmark-scores intermediate (new domain intermediate)

`src/dbt/kipptaf/models/assessments/`, working name
`int_assessments__goal_benchmarks`. Grain: one row per `student_number` x
`academic_year` x `subject`.

Relocates the old view's score-panel assembly out of the rpt layer: the
state-test union (`int_assessments__state_scores`: NJSLA prior year, FAST
PM1/PM3 with the grade-3 same-year read), the i-Ready BOY projections
(`int_assessments__iready_diagnostic_results`, typical-growth levels), and Star
(`stg_renlearn__star`, Miami K-2 fall/spring windows — allowed here; kipptaf
convention is to consume Star at that staging model). Priority pick per student
x subject matches the generator's source order. Columns:
`benchmark_assessment_type`, `performance_level`, `scale_score`,
`is_proficient_int`, `is_approaching_int`, `is_below_int`, `is_tested_int`.

These columns are display and comparison only. Nothing downstream classifies on
them.

This intermediate is shared infrastructure: the DDI Suite and any future
goal-adjacent view read the same panel instead of rebuilding it.

### 4. `rpt_tableau__academic_goals_dashboard` (new reporting view)

`src/dbt/kipptaf/models/extracts/tableau/`. One row per enrolled student x
subject, `academic_year >= 2026`, contract enforced, uniqueness test on
(`academic_year`, `student_number`, `subject`).

Pure joins, no arithmetic, no CASE beyond label cosmetics:

- Roster: `int_extracts__student_enrollments_subjects`, `rn_year = 1`,
  `enroll_status = 0` — grade, school, region, homeroom, IEP status, course
  section and teacher. If course section/teacher are not already carried by the
  roster intermediate, they are added **there** (from
  `base_powerschool__course_enrollments`, a legal edge for a domain
  intermediate), never joined in the rpt.
- Buckets: left join component 2; `coalesce(bucket, 'Bucket 4')` is the one
  piece of logic the rpt owns, and it is what makes a new student with no upload
  land in Bucket 4.
- Scores: left join component 3; `is_tested_int` null-filled to 0.
- Goals: left join `int_assessments__academic_goals` on school x grade x subject
  (Illuminate subject areas mapped to Math/Reading as the old view does),
  projecting all six goal columns under their sheet names (`grade_goal`,
  `school_goal`, `region_goal`, `organization_goal`, `grade_band_goal`,
  `assessment_band_goal`).

A2 note for the PR: no mart covers buckets, goals, or the subject-crossed
roster, so the rpt reads domain intermediates; the PR links an issue for the
missing marts.

### 5. Workbook and exposure

All four tabs repoint to the new view's extract; `miami_goals_new` is deleted
from the workbook. Tableau owns the rollup aggregations:

- Official measures from bucket membership: Bucket 1 share, count of Bucket 2
  (`# to Move`), `(Bucket 1 + Bucket 2) / denominator`
  (`% Proficient with Growth Met`), Bucket 3 and 4 shares.
- A denominator parameter switches every official percentage between all rows
  (enrolled) and `is_tested_int = 1` rows (tested).
- Goal reference lines read the joined sheet columns directly.
- Comparison measures aggregate the score columns, labeled as live-score values.

Add the workbook exposure to `models/exposures/tableau.yml` with the luid in
`asset.metadata.id`, `depends_on` the new rpt. No `cron_schedule` unless the
refresh moves to Dagster.

### 6. Retirement

`rpt_tableau__academic_goals_rollup` is disabled in its properties yml
(`config: enabled: false`), tests disabled with it, SQL and prod relation left
in place as the SY26 record. Its two rows in
`src/dbt/kipptaf/standard-baseline.tsv` come out in the same PR, since a
disabled model no longer parses into the layer check.

## Error handling

- Student in two bucket programs for one subject: uniqueness test fails at error
  severity; fix is in the store, not the model.
- Goal row missing for a school x grade x subject: goal columns come through
  null and the dashboard shows a blank target — visible, not masked. The
  generator's `MissingTargets` gate makes this rare for goaled grades.
- Focus student id with no `student_number` match: surfaces as a
  relationships-style test on the bucket intermediate (warn), since Miami
  enrollment churn can briefly orphan a group member.
- Departed students: roster inner scope drops them everywhere, including from
  official bucket counts, which is the intended enrollment-adjusted behavior.

## Verification

1. Grain tests on both new intermediates and the rpt (uniqueness at error).
2. Bucket reconciliation: for each NJ region x school x grade x subject, compare
   the new view's Bucket 1-3 counts against the generator run manifests
   (committed, non-PII) once the SY27 uploads land. Counts match at upload time;
   later drift is enrollment, which the manifest diff explains.
3. Miami reconciliation: same against the four committed `miami_*` manifests,
   through the Focus branch.
4. Old-vs-new sanity on AY2026 NJ: Bucket 1 share and # to Move from the new
   view against the old view's `student_tier_calculated` distribution, with
   known deltas where the old CASE diverges from the generator's methodology
   (that divergence is the point of the replacement).
5. `uv run dbt build --select <new models>+` locally per `dbt-local-dev`, then
   dbt Cloud CI on the PR.
6. Side-by-side workbook check before the old extract is unpublished.

## Rollout order

1. PR with components 1-4 and 6 (one PR; CI builds the chain).
2. Materialize in prod; run the reconciliations above.
3. Repoint the workbook tabs (Desktop work, outside this repo), publish, add the
   exposure (small follow-up PR if not bundled), retire `miami_goals_new`.

## Open items

- Name check on `int_assessments__goal_benchmarks` before implementation (A3:
  build model, no suffix).
- Whether course section/teacher already sit on
  `int_extracts__student_enrollments_subjects` at the right grain, or move into
  it.
- The missing-marts issue to link for A2 (file at PR time).
- NJ grade 9 and NJGPA goal rows land in the sheet when T&L supplies numbers;
  the view needs no change to pick them up.

## Revision 2026-10-14 (pre-implementation)

Plan-time code reading changed three things:

1. `int_extracts__student_enrollments_subjects` already decodes PowerSchool
   bucket programs inline (`bucket_programs`/`bucket_dedupe` CTEs ->
   `nj_student_tier`, Bucket 4 default) with ~15 downstream consumers, including
   `rpt_illuminate__programs` (the feed that populates Illuminate Student
   Programs) and `rpt_tableau__ddi_dashboard`. Per A4 ("extend instead of adding
   a sibling") and the reuse-identity rule in `src/dbt/kipptaf/CLAUDE.md`,
   `int_students__bucket_assignments` becomes the ONE home for the decode and
   the subjects roster is rewired to read it. Side effect, intended: Miami rows
   of `nj_student_tier` change from a constant Bucket 4 (PowerSchool has no
   Miami) to real Focus-stored tiers, across all consumers. NJ values are
   unchanged (same decode, same latest-assignment pick).
2. Grain carries region: student numbers repeat across PowerSchool instances, so
   the bucket model's key is academic_year x region x student_number x subject,
   and every join to it includes region.
3. The double-upload gate is a latest-assignment-wins pick (matching current
   roster behavior) plus an `n_active_assignments <= 1` warn test, not an
   error-severity uniqueness failure: amendment history legitimately leaves
   exited rows behind, and a hard error would fire on every re-assignment.
4. Known display limitation: the Miami K benchmark panel reads the standard Star
   export (`stg_renlearn__star`) while the generator reads the FAST Star file;
   the panel switches when teamster#5377 stages that file.
5. Focus ids need no crosswalk: the Focus `student_id` (8400-prefixed) IS the
   Miami student number (see `int_focus__students`).
