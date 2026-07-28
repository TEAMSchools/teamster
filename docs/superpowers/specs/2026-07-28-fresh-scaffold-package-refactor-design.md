# FRESH scaffold package refactor — design

Refactor of PR #4488 (`grangel/feat/claude-fresh-scaffold-swap`), stacked as a
single follow-up PR on that branch. Three structural problems and three
code-review findings, resolved together.

## Problems

1. **Package misplacement.** PR #4488 put shared Finalsite/Focus transformation
   logic at the kipptaf level; the `finalsite` and `focus` source-system
   packages were untouched. Source cleaning (grade decode, `enrollment_type`
   defaulting) landed in kipptaf's `stg_finalsite__status_report` union wrapper,
   and a full Focus enrollment derivation (`int_focus__student_enrollments`)
   landed under `kipptaf/models/focus/`.
1. **Novel mode-switch pattern.** `int_finalsite__enrollment_scaffold` is the
   repo's first `exceptions.raise_compiler_error` in a model and its first
   var-driven compile-time mode switch (three SQL programs in one file). The
   `gsheet` and `powerschool` branches are dead code in every real build.
1. **Unjustified project var.** `finalsite_scaffold_source` is read by exactly
   one model, never overridden, and defaults to `blend` in both the model and
   `dbt_project.yml`. Project vars are for cross-project contract values.
1. **Code-review findings** (from the #4488 review): the blend anti-join lacks
   `region` in its key; the reference doc contradicts the shipped
   recruitment-year var; `grade_level = -1` carries two colliding meanings (PK
   and whole-school total).

## Design

### 1. Scaffold collapse (kipptaf)

`int_finalsite__enrollment_scaffold.sql` loses the `finalsite_scaffold_source`
var read, the `raise_compiler_error` guard, and all Jinja branches. The model
becomes the blend pipeline as plain SQL: PowerSchool-derived grade membership
`UNION ALL` sheet rows PowerSchool doesn't have, via anti-join keyed on
`(region, schoolid, grade_level)` — the `region` key is the review fix.

- `finalsite_scaffold_source` is removed from `kipptaf/dbt_project.yml`.
- `finalsite_recruitment_year` stays — it is read at multiple sites and mirrors
  the `current_academic_year` pattern.
- The `scaffold_source` provenance column stays (`powerschool` / `gsheet` — it
  describes rows, not a build mode).
- The model yml drops the mode-switch description.

### 2. Finalsite package promotion

Move from kipptaf's `stg_finalsite__status_report` wrapper into the package
model `src/dbt/finalsite/models/sftp/staging/stg_finalsite__status_report.sql`:

- the `application_grade` → `grade_level` decode (see sentinel scheme below),
- `enrollment_type` initcap + `'New'` default,
- `first_name` initcap,
- `active_school_year_display`.

The kipptaf wrapper shrinks to `union_relations` + region extraction +
`_dbt_source_project` + the `exclude_ids` filter (all inherently cross-district
or kipptaf-only). New package columns are declared in the package properties yml
(staging is contract-enforced).

### 3. Focus package extension

The existing zero-consumer package model
`src/dbt/focus/models/intermediate/int_focus__student_enrollment.sql` absorbs
the Focus-native derivation from PR #4488's kipptaf model:

- students join (name, email, FTEID, dob),
- grade decode (`KG` → 0, `PK` → -1, digits parsed; `short_name = '30'`
  excluded),
- entry/drop code decode and `enroll_status`,
- exit-date default (`June 30` of `syear + 1`),
- school-level decode via `custom_field_select_options`,
- first-day and point-in-time flags (`is_enrolled_fdos`, `is_enrolled_oct01`,
  `is_enrolled_oct15`, `is_enrolled_mar15`, `is_pre_year_withdrawal`),
- `rn_year`, `year_in_school`, `year_in_network`.

kipptaf's `int_focus__student_enrollments` becomes a thin wrapper:
`union_relations` over a new `kippmiami_focus` source table for the package
intermediate, plus the joins that cannot live in the package —
`int_finalsite__contact_id_attributes` (Finalsite-ID crosswalk) and
`stg_google_sheets__people__locations` (location enrichment) — plus
region/`'KTAF'` constants.

The three kipptaf `stg_focus__*` passthroughs added by #4488
(`school_gradelevels`, `student_enrollment_codes`,
`custom_field_select_options`) are deleted along with their
`sources-kippmiami.yml` entries; they existed only to feed the misplaced
intermediate. `sources-kippmiami.yml` instead gains
`int_focus__student_enrollment`.

Naming note: package singular `int_focus__student_enrollment` vs kipptaf plural
`int_focus__student_enrollments` is awkward but matches the
`int_extracts__student_enrollments` shape the wrapper mirrors and avoids
churning downstream refs in #4488.

### 4. Grade-level sentinel scheme

Empirical domains: PowerSchool students carry 0–12 plus 99 (graduated, never
active); Focus grade codes are `PK`/`KG`/01–12 (zero PK enrollments to date);
Finalsite `application_grade` has only K/1st–12th (PK has never appeared); the
scaffold sheet carries -1 (whole-school total) and 0–12.

New scheme:

- **PK → `-1`** at both decode sites (finalsite package staging, focus package
  intermediate). Natural ordering: -1 PK, 0 K, 1–12.
- **Whole-school total → `-9`**, recoded where the sheet enters the model graph
  so the sheet keeps its `-1` entry convention and Ops changes nothing. Every
  `-1` filter/emission site in the FRESH models moves to `-9`:
  `rpt_tableau__fresh_dashboard_progress_to_goals` (`where grade_level = -1` /
  `!= -1` filters and the two `-1 as grade_level` emissions), the
  enrollment/goals scaffold comments and tests, and any goals-sheet model
  carrying `-1` rows (verify during implementation).
- `accepted_values` on finalsite `grade_level` becomes `[-1, 0, 1, …, 12]` at
  `severity: error`, **plus `not_null`** — an unrecognized grade string parses
  to null, and `accepted_values` ignores nulls, so `not_null` is what makes it
  fail loudly. The yml description drops the "mirroring PowerSchool's Pre-K
  convention" claim (PowerSchool has no negative grades in data).
- The equality joins in `rpt_tableau__fresh_dashboard_aggregated` stay correct:
  applicants are 0–12 (future PK: -1), school-total rows are -9 and match
  nothing, as before.

**External coordination:** the Tableau workbook references `-1` for school-total
rows (filters or calculated fields). SRE/Gaby must update the workbook to `-9`
in sync with the merge. Flag on the PR.

### 5. Review fixes and minors folded in

- Region-keyed anti-join (§1).
- `docs/reference/fresh-dashboard-data-model.md`: rewrite the recruitment-year
  section around the `finalsite_recruitment_year` var (the shipped design),
  update lineage for the package moves, delete mode-switch documentation. Same
  treatment for `.claude/skills/fresh-dashboard/SKILL.md`.
- Sentinel collision (§4).
- Drop the redundant `severity: warn` on
  `test_int_finalsite__goals_scaffold_region_matches_scaffold` (project default
  is already `warn`).
- Document the cross-source (frozen PowerSchool vs Focus) dedup precedence in
  `int_tableau__finalsite_student_scaffold`'s `deduplicate_enrollments`, and fix
  the `ps_*` column descriptions that say "PowerSchool" but carry Focus values
  for Miami.
- TODO comment on the syear-only `int_focus__school_year_first_day` join
  (per-school first-day variance flattened; single-region today).
- `rpt_tableau__fresh_dashboard_qc` (disabled, non-compiling): out of scope.
- Gaby's spec/plan docs under `docs/superpowers/` stay untouched (historical
  artifacts of #4488).

### 6. Tests

- The three singular tests from #4488 survive; the region-mismatch test's
  redundant severity override is dropped.
- The extended package `int_focus__student_enrollment` keeps a uniqueness test
  in the package properties yml (intermediate-model requirement).
- The kipptaf wrapper keeps #4488's error-severity `unique` on
  `student_enrollment_id` (guards the Finalsite-ID join fan-out).
- Sentinel scheme covered by the updated `accepted_values` (§4).

### 7. Landing mechanics

Single stacked PR on `grangel/feat/claude-fresh-scaffold-swap` (branch
`cbini/refactor/claude-fresh-scaffold-packages`). Because base ≠ main,
`claude-review` will not run; dbt Cloud CI still does.

Cross-project CI (single-PR workflow per `src/dbt/CLAUDE.md`):

1. Package column adds (`stg_finalsite__status_report`) and the new package
   intermediate columns don't exist in the districts' `zz_stg_*` staging copies
   that kipptaf CI defers to. Force the kipptaf wrappers `state:modified` (SQL
   edit — true here, the wrappers change) AND build the changed package models
   into staging
   (`dbt build --select <models> --project-dir src/dbt/<district> --target staging`)
   so CI's wrapper rebuild sees the new columns. The staging builds recreate
   shared `zz_stg` tables and need direct user authorization at that step.
1. The new `kippmiami_focus` source table (`int_focus__student_enrollment`) must
   exist in staging before kipptaf CI can read it — same staging build covers
   it.
1. Merge sequence: #4488 first, then this PR. Dagster materializes package
   models in each district on deploy.

## Error handling

Nothing silent: staging contracts catch column drift; the `unique` test on
`student_enrollment_id` guards Finalsite-ID fan-out; `accepted_values` +
`not_null` behavior on `grade_level` surfaces any unexpected grade string
(no-digit values parse to null and fail loudly rather than mapping to a
sentinel); the compile-time mode machinery is gone, so there is no dead branch
to rot.

## Out of scope

- Wiring Miami into the blend scaffold (removing the 100%-sheet carve-out) —
  #4488's stated follow-up.
- `rpt_tableau__fresh_dashboard_qc` repair.
- Changing sheet entry conventions (Ops keeps entering `-1` school-total rows).
