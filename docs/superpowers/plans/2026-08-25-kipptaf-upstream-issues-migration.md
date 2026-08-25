# kipptaf Known Upstream Issues Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move model and column semantics out of `src/dbt/kipptaf/CLAUDE.md`
`## Known Upstream Issues` into the owning models' `properties.yml`
descriptions, leaving only directives and cross-model policy resident.

**Architecture:** Each entry is split. The data fact goes to the model's
`properties.yml` `description:`. The directive or prohibition stays in
`src/dbt/kipptaf/CLAUDE.md` as a one-line entry naming the model. Facts about
models that exist in both the `powerschool` package and at kipptaf are written
to both, each describing what is true of that copy. CLAUDE.md is edited last so
the residue is written against what actually landed.

**Tech Stack:** dbt (BigQuery adapter), YAML properties files, `uv run dbt` for
validation, `trunk` for lint.

## Global Constraints

- Worktree: `/workspaces/teamster/.worktrees/cbini-docs-claude-md-audit`.
  Branch: `cbini/docs/claude-md-audit`. All `git` calls use
  `git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit`.
- Design authority:
  `docs/superpowers/specs/2026-08-25-kipptaf-upstream-issues-migration-design.md`.
  Where this plan and the spec disagree, this plan wins — see _Spec corrections_
  below.
- **No description may contain a tracking-issue reference.** `#3900`, `#3915`,
  and `#4407` stay in CLAUDE.md with their directives.
- **No dbt test may be added, removed, or re-scoped by this plan.**
- **No model SQL may be edited by this plan.**
- **No column may be added to a contract-enforced model's yml.** Enforced paths
  at kipptaf: `marts`, `extracts`, `google/sheets/staging`, `people/staging`,
  `schoolmint/grow/staging`, `adp/*/staging`, and others listed in
  `src/dbt/kipptaf/dbt_project.yml`. NOT enforced: `powerschool/staging`,
  `powerschool/intermediate`. Editing an existing column's `description:` is
  always safe.
- YAML: an unquoted multi-line `description:` cannot start with a backtick or
  contain a colon followed by a space. Match the block-scalar style the file
  already uses. Lead with a word; use an em dash instead of a colon.
- Do not reorder `columns:` entries. Adding a description does not add a test,
  so no column changes sort position. A reorder in a diff is a mistake.

## Spec corrections

The spec was written before the target files were inspected. Four of its
assumptions are wrong, and all four reduce scope. This plan implements the
corrected version.

1. **Entry 12 (Grow `_dagster_partition_key`) needs no yml edit.** Both
   `stg_schoolmint_grow__measurements.yml` and
   `stg_schoolmint_grow__rubrics__measurement_groups__measurements.yml` already
   document the deviation in their model descriptions. `schoolmint/grow/staging`
   is contract-enforced and `_dagster_partition_key` is absent from both column
   lists, so there is no column-level home for it. This entry becomes a
   CLAUDE.md deletion only.
1. **Entry 2 (`campus_crosswalk`) is mostly already written.** Its description
   already names it sole owner of location-to-campus and already documents the
   `rpt_illuminate__roles` inner join. Only the grain sentence is missing.
1. **Entry 13 (`locations` column naming) is half already written.**
   `location_region` already carries its long-form-name description. Only `city`
   needs extending.
1. **The `entity` fragment of entry 14 cannot go on `dim_staff`.** `marts` is
   contract-enforced, so `dim_staff`'s 16 columns are its complete column set,
   and `entity` is not among them — it is a column on `rpt_tableau__*` extracts.
   That sentence stays in CLAUDE.md; only the grain fact moves.

---

### Task 1: powerschool package staging facts

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__students.yml`
- Modify:
  `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__cc.yml`

**Interfaces:**

- Consumes: nothing.
- Produces: the package-level wording that Task 2's kipptaf descriptions
  complement. Task 2 describes the union view's filtering; this task describes
  the raw defect.

- [ ] **Step 1: Extend the `dcid` column description in
      `stg_powerschool__students.yml`**

Current text is `Unique identifier for this table. Indexed. Required.` Replace
with:

```yaml
description: >-
  Unique identifier for this table. Indexed. Required. PowerSchool retains four
  placeholder rows per district carrying dcid -100, student_number 0, and
  enroll_status -100. They are not real students.
```

- [ ] **Step 2: Extend the `enroll_status` column description in
      `stg_powerschool__students.yml`**

Current text is `The enrollment status of the student.` Replace with:

```yaml
description: >-
  The enrollment status of the student. Values are -1 pre-registered, 0 active,
  1 inactive, 2 withdrawn, and 3 graduated. The value is student-level, not
  per-stint — every enrollment stint for a student carries the same value, and
  it reflects current status only, never status on a past date.
```

- [ ] **Step 3: Extend the model description in `stg_powerschool__cc.yml`**

Current text is
`This table maintains the student schedules. It contains information such as Section ID, Student ID, Term ID and Teacher ID.`
Replace with:

```yaml
description: >-
  This table maintains the student schedules. It contains information such as
  Section ID, Student ID, Term ID and Teacher ID. Carries a frozen historical
  corpus of PowerSchool double-writes — duplicate rows for the same student,
  section, and dateleft combination. A warn-level uniqueness test on those three
  columns surfaces them.
```

- [ ] **Step 4: Verify the YAML parses and no node changed**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit
uv run dbt parse --no-partial-parse --target prod \
  --project-dir src/dbt/kippnewark
```

Expected: completes without error. `powerschool` is a package with no resolvable
vars standalone, so it is parsed through a consuming district. A parse error
naming either edited file means the YAML is malformed — fix and re-run before
committing.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit add \
  src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__students.yml \
  src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__cc.yml
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit commit -m "docs(dbt): document powerschool staging placeholder rows and double-writes"
```

---

### Task 2: kipptaf powerschool union-view facts

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__students.yml`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__cc.yml`

**Interfaces:**

- Consumes: Task 1's package wording. These descriptions state what the union
  view does about the defect, not the defect itself.
- Produces: nothing later tasks depend on.

Both files are thin — `stg_powerschool__students.yml` lists one column
(`student_number`) and has no model description; `stg_powerschool__cc.yml` lists
no columns and has no model description. `powerschool/staging` is NOT
contract-enforced at kipptaf, so adding a column entry is safe here.

- [ ] **Step 1: Add a model description to `stg_powerschool__students.yml`**

Insert as a sibling of `name:`, above `columns:`:

```yaml
description: >-
  Cross-district union of the district-level stg_powerschool__students models.
  Filters out PowerSchool's placeholder rows with a dcid >= 1 predicate, so the
  four per-district placeholders present in the raw district tables do not
  appear here.
```

- [ ] **Step 2: Add an `enroll_status` column entry to
      `stg_powerschool__students.yml`**

Append to the existing `columns:` list, after `student_number`:

```yaml
- name: enroll_status
  description: >-
    Enrollment status of the student. Values are -1 pre-registered, 0 active, 1
    inactive, 2 withdrawn, and 3 graduated. Student-level, not per-stint, and
    current-only — it never reflects status on a past date.
```

- [ ] **Step 3: Add a model description to `stg_powerschool__cc.yml`**

Insert as a sibling of `name:`:

```yaml
description: >-
  Cross-district union of the district-level stg_powerschool__cc models.
  Inherits the frozen PowerSchool double-write corpus described on the
  package-level model — duplicate rows for the same student, section, and
  dateleft combination.
```

- [ ] **Step 4: Verify the YAML parses**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit
uv run dbt parse --no-partial-parse --target prod \
  --project-dir src/dbt/kipptaf
```

Expected: completes without error.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit add \
  src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__students.yml \
  src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__cc.yml
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit commit -m "docs(dbt): document kipptaf powerschool union view filtering"
```

---

### Task 3: student enrollment union graduate placeholders

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__student_enrollment_union.yml`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__student_enrollment_union.yml`

**Interfaces:**

- Consumes: the `enroll_status` value meanings written in Tasks 1 and 2. Do not
  restate them here; reference the status by name.
- Produces: nothing later tasks depend on.

The package file has no model description and no descriptions on `entrydate`,
`exitdate`, or `enroll_status`. The kipptaf file already has a good model
description and lists only two columns. Neither path is contract-enforced.

- [ ] **Step 1: Add a model description to the package file**

Insert as a sibling of `name:`:

```yaml
description: >-
  One row per student-school enrollment event. Graduated students carry
  placeholder rows with null entry and exit dates, one row per academic year per
  student and district. Surrogate keys must include academic_year or those rows
  collide.
```

- [ ] **Step 2: Add descriptions to `entrydate` and `exitdate` in the package
      file**

```yaml
- name: entrydate
  description: >-
    Date the student entered the school for this stint. Null on graduate
    placeholder rows, which a date-range join silently drops.
- name: exitdate
  description: >-
    Date the student left the school for this stint. Null on graduate
    placeholder rows, which a date-range join silently drops.
```

- [ ] **Step 3: Extend the kipptaf model description**

Append to the existing description, preserving its current text:

```text
Graduated students carry placeholder rows with null entry and exit dates,
one row per academic year per student and district. Retain them —
downstream enrollment models and dim_student_enrollments are
alumni-inclusive by design.
```

- [ ] **Step 4: Verify both projects parse**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit
uv run dbt parse --no-partial-parse --target prod --project-dir src/dbt/kippnewark
uv run dbt parse --no-partial-parse --target prod --project-dir src/dbt/kipptaf
```

Expected: both complete without error.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit add \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__student_enrollment_union.yml \
  src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__student_enrollment_union.yml
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit commit -m "docs(dbt): document graduate placeholder rows on enrollment union"
```

---

### Task 4: people and location models

**Files:**

- Modify:
  `src/dbt/kipptaf/models/people/intermediate/properties/int_people__location_crosswalk.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__campus_crosswalk.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__locations.yml`
- Modify:
  `src/dbt/kipptaf/models/people/staging/properties/stg_people__employee_numbers.yml`

**Interfaces:**

- Consumes: nothing.
- Produces: nothing later tasks depend on.

`google/sheets/staging` and `people/staging` are contract-enforced. Edit
existing descriptions only — do not add column entries in those two files.

- [ ] **Step 1: Extend the `int_people__location_crosswalk` model description**

Append to the existing description, preserving its current text:

```text
Despite the name, this is not a union model and carries no
_dbt_source_relation column. To join it across regions, match the other
side's _dbt_source_project against location_dagster_code_location.
```

- [ ] **Step 2: Extend the `campus_crosswalk` model description**

The description already covers sole ownership and the `rpt_illuminate__roles`
inner join. Append only the grain sentence, preserving the existing text:

```text
Grain is Location_Name alone. Name is the parent campus and repeats across
sibling schools. The sheet carries no self-referential rows, so a campus
record resolves to a null campus name by design.
```

- [ ] **Step 3: Extend the `city` column description in
      `stg_google_sheets__people__locations.yml`**

Current text is `City where the location is situated.` Replace with:

```yaml
description: >-
  City where the location is situated. Holds the short canonical region names —
  Newark, Camden, Miami, Paterson — so region lookups by short name use this
  column rather than location_region, which holds long-form legal-entity names.
```

- [ ] **Step 4: Add a model description to `stg_people__employee_numbers.yml`**

The file has no model description. Insert as a sibling of `name:`:

```yaml
description: >-
  Assigns one employee number per ADP associate id, in first-appearance order. A
  lower number means the associate was seen in ADP earlier, NOT that they were
  hired earlier — worker_original_hire_date is editable. One person with
  duplicate ADP worker records receives multiple active employee numbers.
```

- [ ] **Step 5: Verify the project parses**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit
uv run dbt parse --no-partial-parse --target prod --project-dir src/dbt/kipptaf
```

Expected: completes without error. A contract error naming
`stg_google_sheets__people__locations` or `stg_people__employee_numbers` means a
column was added rather than edited — revert that edit.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit add \
  src/dbt/kipptaf/models/people/intermediate/properties/int_people__location_crosswalk.yml \
  src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__campus_crosswalk.yml \
  src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__locations.yml \
  src/dbt/kipptaf/models/people/staging/properties/stg_people__employee_numbers.yml
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit commit -m "docs(dbt): document location crosswalk grain and employee number ordering"
```

---

### Task 5: dim_terms and dim_staff

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/properties/dim_terms.yml`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff.yml`

**Interfaces:**

- Consumes: nothing.
- Produces: nothing later tasks depend on.

`marts` is contract-enforced. Edit existing descriptions only. `dim_staff` has
no `entity` column — do not add one, and do not move the `entity` sentence here.
It stays in CLAUDE.md per _Spec corrections_ item 4.

- [ ] **Step 1: Extend the `type` column description in `dim_terms.yml`**

Current text is
`Category of period (e.g., academic, PM, survey, assessment, fiscal).` Replace
with:

```yaml
description: >-
  Category of period. KIPP-managed and sourced from
  stg_google_sheets__reporting__terms, not derived from PowerSchool. Values
  include RT for reporting term at quarter grain, ATT for attendance at semester
  or year grain, plus LIT, AR, REP, and SURVEY. Quarter attendance rows live
  under RT with term_name Q1 through Q4 — not under ATT, and not keyed by
  term_code RT1 through RT4.
```

- [ ] **Step 2: Extend the `dim_staff` model description**

Append to the existing description, preserving its current text:

```text
This dimension is all-time staff, roughly 4,600 rows, not active-only. For
an active-staff grain, spine on dim_staff_work_assignments where
is_current, which already excludes terminated staff by termination date.
```

- [ ] **Step 3: Verify the project parses and contracts hold**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit
uv run dbt parse --no-partial-parse --target prod --project-dir src/dbt/kipptaf
```

Expected: completes without error.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit add \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_terms.yml \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff.yml
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit commit -m "docs(dbt): document dim_terms type values and dim_staff grain"
```

---

### Task 6: renlearn and ADP

**Files:**

- Modify:
  `src/dbt/kipptaf/models/renlearn/staging/properties/stg_renlearn__star.yml`
- Modify:
  `src/dbt/kipptaf/models/adp/workforce_now/api/staging/properties/stg_adp_workforce_now__workers.yml`

**Interfaces:**

- Consumes: nothing.
- Produces: nothing later tasks depend on.

`stg_renlearn__star.yml` has no model description and 136 columns.
`adp/workforce_now/api/staging` is contract-enforced — edit the existing model
description only.

- [ ] **Step 1: Add a model description to `stg_renlearn__star.yml`**

Insert as a sibling of `name:`:

```yaml
description: >-
  Consolidated STAR model and the single place STAR data is read or edited.
  Materialized as a table. Folds in the derived columns that previously lived in
  the retired rollup — academic_year, star subject and discipline,
  administration window mapped from Fall, Winter, and Spring to BOY, MOY, and
  EOY, benchmark integer flags, and the per-subject row numbers.
```

- [ ] **Step 2: Extend the `stg_adp_workforce_now__workers` model description**

Append to the existing description, preserving its current text:

```text
There is no SCD2 tombstone for disappearance. A worker hard-deleted or
merged in ADP vanishes from the daily snapshots without a terminated status
row, so its final record stays open at 9999-12-31 with is_current_record
true indefinitely. That ghost flows downstream into employee numbers, the
staff roster, and the RapidIdentity login feed.
```

- [ ] **Step 3: Verify the project parses**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit
uv run dbt parse --no-partial-parse --target prod --project-dir src/dbt/kipptaf
```

Expected: completes without error.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit add \
  src/dbt/kipptaf/models/renlearn/staging/properties/stg_renlearn__star.yml \
  src/dbt/kipptaf/models/adp/workforce_now/api/staging/properties/stg_adp_workforce_now__workers.yml
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit commit -m "docs(dbt): document consolidated STAR model and ADP ghost records"
```

---

### Task 7: rewrite the CLAUDE.md section

**Files:**

- Modify: `src/dbt/kipptaf/CLAUDE.md` — the `## Known Upstream Issues` section

**Interfaces:**

- Consumes: every description written in Tasks 1 through 6. Before writing,
  re-read them so the residue does not restate a fact that now lives in a yml.
- Produces: the final resident text.

The rewritten section keeps three things: the three cross-model policy entries
verbatim, one-line directives naming the model for each split entry, and every
tracking-issue reference.

- [ ] **Step 1: Confirm what actually landed**

Run:

```bash
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit diff \
  --stat HEAD~6..HEAD -- src/dbt
```

Expected: the 14 properties.yml files from Tasks 1 through 6. If a file is
missing, the residue for its entry must not claim the fact moved.

- [ ] **Step 2: Replace the section body with the directives**

Keep the `## Known Upstream Issues` heading. Keep entries 6, 8, and 9 — "Miami
is the exception, deliberately", "Point-in-time enrollment headcount uses
entry/exit dates", and "School calendars diverge at year-end" — byte for byte.
Replace the other 14 entries with:

```markdown
Model and column semantics for these live in each model's properties yml. What
stays here is what to do and what not to do.

- **`stg_powerschool__students`** — never resolve identity or attribute facts
  against `enroll_status` `-1` or `1`. Apply the `dcid >= 1` placeholder filter
  when reading a per-region staging table directly.
- **`int_powerschool__student_enrollment_union`** — retain graduate placeholder
  rows; derived enrollment models and `dim_student_enrollments` stay
  alumni-inclusive. Include `academic_year` in surrogate key inputs.
- **`stg_powerschool__cc` double-writes** — filter `is_dropped_section` first
  when date-range joining `base_powerschool__course_enrollments`. Do NOT add
  defensive dedupes (`qualify row_number() = 1` or `dbt_utils.deduplicate()`)
  for the residual fan-out. Downgrade the affected mart PK uniqueness test to
  `severity: warn` with a `TODO(#3915)` so it returns to error when source
  cleanup completes. `base_powerschool__student_enrollments` date-range joins
  currently need no tiebreaker. Tracked in
  [#3900](https://github.com/TEAMSchools/teamster/issues/3900); Ops cleanup in
  [#3915](https://github.com/TEAMSchools/teamster/issues/3915).
- **`int_people__location_crosswalk`** — consumers joining on an aliased name
  (e.g. `fct_staff_observations` on `gro.school_name`) must use this model.
  Canonical-grain consumers, meaning one row per logical school, use
  `stg_google_sheets__people__locations`.
- **`stg_google_sheets__people__campus_crosswalk`** — do not reintroduce a
  `Campus_Name` scalar on the locations sheet.
- **`stg_google_sheets__people__locations`** — to map `_dbt_source_project` to a
  region, use `dim_regions.dagster_code_location`, not this model.
- **SchoolMint Grow archived rows** — `stg_schoolmint_grow__measurements` and
  `stg_schoolmint_grow__rubrics__measurement_groups__measurements` deliberately
  do not filter to non-archived. Don't re-add the filter to those two without
  understanding the FK-coverage tradeoff.
- **`dim_staff`** — do NOT filter
  `dim_work_assignment_status.status_name != 'Terminated'` to get "active". That
  field is misaligned with the roster's `worker_status_code` and over-drops
  roughly 100 roster-active staff. The roster active-and-primary set (~1,526)
  runs ~30 larger than the marts' current-primary set, from hire and termination
  timing. On the `rpt_tableau__*` extracts, `entity` (KTAF vs Region) derives
  from `business_unit_name` — `KIPP TEAM and Family Schools Inc.` is KTAF,
  anything else is Region.
- **`stg_renlearn__star`** — `int_renlearn__star_rollup` is disabled
  (`config: enabled: false`); leave it. Edit and consume STAR at
  `stg_renlearn__star`.
- **`stg_adp_workforce_now__workers` ghosts** — fix by rematerializing the ADP
  `workers` partitions spanning the record's active dates; the re-pull drops the
  ghost and downstream tables rebuild via automation. Detection check tracked in
  [#4407](https://github.com/TEAMSchools/teamster/issues/4407).
```

- [ ] **Step 3: Verify no fact was left duplicated**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit
grep -nE 'dcid = -100|9999-12-31|first-appearance|4,600|uniqueness grain|BOY' \
  src/dbt/kipptaf/CLAUDE.md
```

Expected: no matches. Each of those strings is a data fact that now lives in a
yml. A match means the residue restates a moved fact — delete that clause.

- [ ] **Step 4: Verify the section shrank as designed**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit
awk '/^## Known Upstream Issues/,/^## Exposures/' src/dbt/kipptaf/CLAUDE.md | wc -c
```

Expected: roughly 5,200 characters, down from 9,058 — about 2,100 for the three
kept policy entries plus about 3,050 for the directive list. A number above
7,000 means facts were kept that should have moved.

- [ ] **Step 5: Lint**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit
~/.cache/trunk/launcher/trunk check --force --no-fix src/dbt/kipptaf/CLAUDE.md </dev/null
```

Expected: no markdownlint issues. MD060 table-padding findings are fixed by the
pre-commit format hook and can be committed as-is.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit add src/dbt/kipptaf/CLAUDE.md
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit commit -m "docs(claude): reduce kipptaf upstream issues to directives"
```

---

### Task 8: whole-branch verification

**Files:** none modified.

**Interfaces:**

- Consumes: all prior tasks.
- Produces: the evidence needed to open the PR.

- [ ] **Step 1: Confirm no test, SQL, or column-list changed**

Run:

```bash
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit diff \
  origin/main...HEAD --stat
```

Expected: only `.md` and `properties/*.yml` files. Any `.sql` file in the list
violates a global constraint — stop and report.

Run:

```bash
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit diff \
  origin/main...HEAD -- '*.yml' | grep -E '^[+-]\s*- (unique|not_null|relationships|accepted_values)'
```

Expected: no output. Any match means a test was added or removed.

- [ ] **Step 2: Confirm no description carries an issue reference**

Run:

```bash
git -C /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit diff \
  origin/main...HEAD -- '*.yml' | grep -nE '^\+.*#[0-9]{4}'
```

Expected: no output.

- [ ] **Step 3: Full parse of both entry points**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit
uv run dbt parse --no-partial-parse --target prod --project-dir src/dbt/kipptaf
uv run dbt parse --no-partial-parse --target prod --project-dir src/dbt/kippnewark
```

Expected: both complete without error.

- [ ] **Step 4: Lint every changed file**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-docs-claude-md-audit
~/.cache/trunk/launcher/trunk check --force --no-fix \
  $(git diff --name-only origin/main...HEAD | xargs -I{} sh -c 'test -f {} && echo {}') </dev/null
```

Expected: no issues. `yamllint` fires here and not at the pre-commit hook, so
this step is the one that catches quoting and octal-value problems.

- [ ] **Step 5: Report, do not push**

Summarize what changed and hand the push to the user. Do not open a PR without
being asked.

State plainly in the summary that dbt Cloud CI will be a trivial no-op — a
`description:` edit does not mark a model `state:modified` — so CI passing is
**not** validation of this branch.

## Notes for the implementer

- `powerschool` is a package with no resolvable vars standalone. Parse and build
  it through a consuming district project-dir, which is why Task 1 parses
  `kippnewark`.
- If `dbt parse` fails with a missing `dbt_packages/` error, run
  `uv run dbt deps --project-dir src/dbt/<project>` once. A fresh worktree has
  no installed packages.
- Every description in this plan is written to avoid a leading backtick and a
  colon-space, which is why identifiers appear unbackticked inside description
  prose. That is deliberate — do not "fix" it by adding backticks.
