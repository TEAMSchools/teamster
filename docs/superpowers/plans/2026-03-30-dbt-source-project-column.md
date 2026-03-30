# `_dbt_source_project` Column Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace runtime `regexp_extract` joins (`union_dataset_join_clause`)
with a pre-computed `_dbt_source_project` column on cross-district union models.

**Architecture:** Add `_dbt_source_project` (via a renamed
`extract_source_project` macro) to every cross-district `union_relations` model
in kipptaf. Replace all 268 downstream `union_dataset_join_clause` calls with
direct column comparisons. Remove the old macro.

**Tech Stack:** dbt (BigQuery dialect), Jinja, YAML

**Spec:**
`docs/superpowers/specs/2026-03-30-dbt-source-project-column-design.md`

**Worktree:** `.worktrees/cbini/refactor/claude-dbt-source-project-column`

**Working directory for all paths below:** `src/dbt/kipptaf/`

---

## File Structure

| Category                            | Files | Change                           |
| ----------------------------------- | ----- | -------------------------------- |
| `macros/utils.sql`                  | 1     | Rename macro, remove old macro   |
| Cross-district union models (SQL)   | ~87   | Add `_dbt_source_project` column |
| Properties YAML (contract-enforced) | ~45   | Add column declaration           |
| Downstream models using macro       | ~93   | Replace macro with column join   |
| `CLAUDE.md`                         | 1     | Update documentation             |

---

## Reference: Two SQL Patterns

Every union model falls into one of two patterns. Tasks reference these by name.

### Pattern A: "Direct select" (majority)

The entire model is just the `union_relations` call. Wrap it in a CTE:

**Before:**

```sql
{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__students"),
            source("kippcamden_powerschool", "stg_powerschool__students"),
            source("kippmiami_powerschool", "stg_powerschool__students"),
            source("kipppaterson_powerschool", "stg_powerschool__students"),
        ]
    )
}}
```

**After:**

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "stg_powerschool__students",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "stg_powerschool__students",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "stg_powerschool__students",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "stg_powerschool__students",
                    ),
                ]
            )
        }}
    )

select
    *,
    {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

### Pattern B: "CTE-wrapped" (already has CTEs)

Add the column to the select that first exposes the union output.

**Before (`stg_powerschool__storedgrades.sql`):**

```sql
select u.*, if(l.name is null, true, false) as is_transfer_grade,
from union_relations as u
left join ...
```

**After:**

```sql
select
    u.*,
    {{ extract_source_project("u") }} as _dbt_source_project,
    if(l.name is null, true, false) as is_transfer_grade,
from union_relations as u
left join ...
```

### YAML pattern (contract-enforced models)

Add immediately after `_dbt_source_relation`:

```yaml
- name: _dbt_source_project
  data_type: string
```

---

## Task 1: Rename macro and remove `union_dataset_join_clause`

**Files:**

- Modify: `macros/utils.sql`

- [ ] **Step 1: Rewrite `macros/utils.sql`**

Replace the entire file with:

```sql
{% macro extract_source_project(relation) %}
    regexp_extract({{ relation }}._dbt_source_relation, r'(kipp\w+)_')
{% endmacro %}
```

This renames `extract_code_location` → `extract_source_project` and removes
`union_dataset_join_clause`. The old macro will error on any remaining callers,
which is intentional — it ensures we catch missed replacements at compile time.

- [ ] **Step 2: Commit**

```bash
git add macros/utils.sql
git commit -m "refactor: rename extract_code_location, remove union_dataset_join_clause (#3142)"
```

> **Note:** Do NOT run `dbt compile` yet — downstream models still reference the
> removed macro. We will validate after all replacements are complete.

---

## Task 2: Add `_dbt_source_project` to PowerSchool staging models

**Files (all Pattern A — direct select, all under
`models/powerschool/staging/`):**

- `stg_powerschool__assignmentscore.sql`
- `stg_powerschool__attendance.sql`
- `stg_powerschool__attendance_code.sql`
- `stg_powerschool__calendar_day.sql`
- `stg_powerschool__cc.sql`
- `stg_powerschool__courses.sql`
- `stg_powerschool__fte.sql`
- `stg_powerschool__gen.sql`
- `stg_powerschool__gpnode.sql`
- `stg_powerschool__gpprogresssubject.sql`
- `stg_powerschool__gpprogresssubjectearned.sql`
- `stg_powerschool__gpprogresssubjectenrolled.sql`
- `stg_powerschool__pgfinalgrades.sql`
- `stg_powerschool__roledef.sql`
- `stg_powerschool__s_nj_crs_x.sql`
- `stg_powerschool__s_nj_ren_x.sql`
- `stg_powerschool__s_nj_stu_x.sql`
- `stg_powerschool__s_stu_x.sql`
- `stg_powerschool__schools.sql`
- `stg_powerschool__sectionteacher.sql`
- `stg_powerschool__studentrace.sql`
- `stg_powerschool__students.sql`
- `stg_powerschool__studenttest.sql`
- `stg_powerschool__studenttestscore.sql`
- `stg_powerschool__terms.sql`
- `stg_powerschool__test.sql`
- `stg_powerschool__testscore.sql`
- `stg_powerschool__u_storedgrades_de.sql`
- `stg_powerschool__u_studentsuserfields.sql`
- `stg_powerschool__userscorefields.sql`

**Files (Pattern B — CTE-wrapped):**

- `stg_powerschool__log.sql` (CTE: `union_relations`)
- `stg_powerschool__storedgrades.sql` (CTE: `union_relations`)
- `stg_powerschool__users.sql` (CTE: `union_relations`)

- [ ] **Step 1: Apply Pattern A to all direct-select models**

For each direct-select model, wrap the `dbt_utils.union_relations(...)` call in
a CTE and add the `_dbt_source_project` column. Follow the Pattern A template
from the Reference section above. Each model has its own set of sources — read
the file to get the correct `relations` list.

- [ ] **Step 2: Apply Pattern B to CTE-wrapped models**

For each CTE-wrapped model, add
`{{ extract_source_project("<alias>") }} as _dbt_source_project,` to the first
select that exposes the union output. Read each file to identify the correct
alias and insertion point.

- [ ] **Step 3: Update properties YAML**

For every staging model that has a properties YAML file listing
`_dbt_source_relation`, add `_dbt_source_project` immediately after it. Property
files live in `models/powerschool/staging/properties/`. Search with:

```bash
grep -rl "_dbt_source_relation" models/powerschool/staging/properties/
```

Add to each matching file:

```yaml
- name: _dbt_source_project
  data_type: string
```

- [ ] **Step 4: Commit**

```bash
git add models/powerschool/staging/
git commit -m "refactor(powerschool): add _dbt_source_project to staging models (#3142)"
```

---

## Task 3: Add `_dbt_source_project` to PowerSchool base models

**Files (all under `models/powerschool/base/`):**

- `base_powerschool__course_enrollments.sql` (Pattern B)
- `base_powerschool__final_grades.sql` (Pattern A or B — read to confirm)
- `base_powerschool__sections.sql` (Pattern B)
- `base_powerschool__student_enrollments.sql` (Pattern B)

- [ ] **Step 1: Read each file and add `_dbt_source_project`**

These are complex models with multiple CTEs and joins. Read each file fully. Add
`{{ extract_source_project("<alias>") }} as _dbt_source_project,` to the first
select that exposes the union output. Use the alias that refers to the
`union_relations` CTE.

- [ ] **Step 2: Update properties YAML**

Search `models/powerschool/base/properties/` for files listing
`_dbt_source_relation` and add `_dbt_source_project` after it.

- [ ] **Step 3: Commit**

```bash
git add models/powerschool/base/
git commit -m "refactor(powerschool): add _dbt_source_project to base models (#3142)"
```

---

## Task 4: Add `_dbt_source_project` to PowerSchool intermediate models

**Files (all under `models/powerschool/intermediate/`):**

- `int_powerschool__ada.sql`
- `int_powerschool__attendance_streak.sql`
- `int_powerschool__calendar_rollup.sql`
- `int_powerschool__calendar_week.sql`
- `int_powerschool__category_grades.sql`
- `int_powerschool__category_grades_pivot.sql`
- `int_powerschool__district_entry_date.sql`
- `int_powerschool__final_grades_pivot.sql`
- `int_powerschool__gpa_cumulative.sql`
- `int_powerschool__gpa_term.sql`
- `int_powerschool__gradebook_assignments.sql`
- `int_powerschool__gradescaleitem_lookup.sql`
- `int_powerschool__ps_adaadm_daily_ctod.sql`
- `int_powerschool__section_grade_config.sql`
- `int_powerschool__spenrollments.sql`
- `int_powerschool__student_contacts.sql`
- `int_powerschool__teacher_grade_levels.sql`
- `int_powerschool__teachers.sql`
- `int_powerschool__terms.sql`

- [ ] **Step 1: Read each file and add `_dbt_source_project`**

Most are Pattern A (direct select). Some may be Pattern B. Read each file to
determine the pattern, then apply the corresponding transformation.

- [ ] **Step 2: Update properties YAML**

Search `models/powerschool/intermediate/properties/` for files listing
`_dbt_source_relation` and add `_dbt_source_project` after it.

- [ ] **Step 3: Commit**

```bash
git add models/powerschool/intermediate/
git commit -m "refactor(powerschool): add _dbt_source_project to intermediate models (#3142)"
```

---

## Task 5: Add `_dbt_source_project` to Deanslist models

**Files (all Pattern A — direct select):**

- `models/deanslist/api/staging/stg_deanslist__behavior.sql`
- `models/deanslist/api/staging/stg_deanslist__terms.sql`
- `models/deanslist/api/staging/stg_deanslist__users.sql`
- `models/deanslist/api/intermediate/int_deanslist__comm_log.sql`
- `models/deanslist/api/intermediate/int_deanslist__incidents.sql`
- `models/deanslist/api/intermediate/int_deanslist__incidents__attachments.sql`
- `models/deanslist/api/intermediate/int_deanslist__incidents__penalties.sql`
- `models/deanslist/api/intermediate/int_deanslist__roster_assignments.sql`
- `models/deanslist/api/intermediate/int_deanslist__students__custom_fields__pivot.sql`

- [ ] **Step 1: Apply Pattern A to all models**

- [ ] **Step 2: Update properties YAML**

Search `models/deanslist/` for YAML files listing `_dbt_source_relation` and add
`_dbt_source_project` after it.

- [ ] **Step 3: Commit**

```bash
git add models/deanslist/
git commit -m "refactor(deanslist): add _dbt_source_project to union models (#3142)"
```

---

## Task 6: Add `_dbt_source_project` to iReady models

**Files:**

- `models/iready/staging/stg_iready__personalized_instruction_summary.sql`
  (Pattern A)
- `models/iready/intermediate/int_iready__diagnostic_results.sql` (Pattern B,
  CTE: `union_relations`)
- `models/iready/intermediate/int_iready__instruction_by_lesson.sql` (Pattern B,
  CTE: `union_relations`)
- `models/iready/intermediate/int_iready__instruction_by_lesson_pro.sql`
  (Pattern B, CTE: `union_relations`)
- `models/iready/intermediate/int_iready__instructional_usage_data.sql` (Pattern
  B, CTE: `union_relations`)
- `models/iready/intermediate/int_iready__personalized_instruction_unpivot.sql`
  (Pattern B, CTE: `union_relations`)

- [ ] **Step 1: Apply Pattern A to the staging model**

- [ ] **Step 2: Apply Pattern B to intermediate models**

Read each file. Add
`{{ extract_source_project("<alias>") }} as _dbt_source_project,` to the first
select exposing the union output.

- [ ] **Step 3: Update properties YAML**

Search `models/iready/` for YAML files listing `_dbt_source_relation` and add
`_dbt_source_project` after it.

- [ ] **Step 4: Commit**

```bash
git add models/iready/
git commit -m "refactor(iready): add _dbt_source_project to union models (#3142)"
```

---

## Task 7: Add `_dbt_source_project` to Pearson models

**Files (all Pattern A — direct select, all under `models/pearson/staging/`):**

- `stg_pearson__njgpa.sql`
- `stg_pearson__njsla.sql`
- `stg_pearson__njsla_science.sql`
- `stg_pearson__parcc.sql`
- `stg_pearson__student_list_report.sql`
- `stg_pearson__student_test_update.sql`

- [ ] **Step 1: Apply Pattern A to all models**

- [ ] **Step 2: Update properties YAML if applicable**

Search `models/pearson/` for YAML files listing `_dbt_source_relation`.

- [ ] **Step 3: Commit**

```bash
git add models/pearson/
git commit -m "refactor(pearson): add _dbt_source_project to staging models (#3142)"
```

---

## Task 8: Add `_dbt_source_project` to Overgrad models

**Files:**

- `models/overgrad/staging/stg_overgrad__admissions.sql` (Pattern A)
- `models/overgrad/intermediate/int_overgrad__admissions.sql` (Pattern A or B —
  read to confirm)
- `models/overgrad/intermediate/int_overgrad__students.sql` (Pattern A or B —
  read to confirm)

- [ ] **Step 1: Read each file, apply Pattern A or B**

- [ ] **Step 2: Update properties YAML if applicable**

- [ ] **Step 3: Commit**

```bash
git add models/overgrad/
git commit -m "refactor(overgrad): add _dbt_source_project to union models (#3142)"
```

---

## Task 9: Add `_dbt_source_project` to remaining source systems

**Amplify:**

- `models/amplify/mclass/sftp/staging/stg_amplify__mclass__sftp__benchmark_student_summary.sql`
  (Pattern A)
- `models/amplify/mclass/sftp/staging/stg_amplify__mclass__sftp__pm_student_summary.sql`
  (Pattern B, CTE: `union_relations`)

**Edplan:**

- `models/edplan/intermediate/int_edplan__njsmart_powerschool_union.sql`
  (Pattern A)

**Finalsite:**

- `models/finalsite/staging/stg_finalsite__status_report.sql` (Pattern B, CTE:
  `union_relations`)

**Renlearn:**

- `models/renlearn/staging/stg_renlearn__star.sql` (Pattern B, CTE:
  `union_relations`)
- `models/renlearn/staging/stg_renlearn__fast_star.sql` (Pattern A)
- `models/renlearn/staging/stg_renlearn__star_dashboard_standards.sql` (Pattern
  A)

**Titan:**

- `models/titan/staging/stg_titan__person_data.sql` (Pattern A)

- [ ] **Step 1: Apply Pattern A or B to each model**

Read each file to confirm the pattern. Apply the transformation.

- [ ] **Step 2: Update properties YAML if applicable**

Search each system's directory for YAML files listing `_dbt_source_relation`.

- [ ] **Step 3: Commit**

```bash
git add models/amplify/ models/edplan/ models/finalsite/ models/renlearn/ models/titan/
git commit -m "refactor: add _dbt_source_project to amplify, edplan, finalsite, renlearn, titan (#3142)"
```

---

## Task 10: Replace all downstream `union_dataset_join_clause` usages

**Scope:** ~93 files, ~268 usages across `models/`. Every instance follows the
exact pattern:

```sql
{{ union_dataset_join_clause(left_alias="X", right_alias="Y") }}
```

**Replacement rule:** For each usage, replace with:

```sql
X._dbt_source_project = Y._dbt_source_project
```

Where `X` and `Y` are the literal alias values from `left_alias` and
`right_alias`.

- [ ] **Step 1: Find all files with usages**

```bash
grep -rl "union_dataset_join_clause" models/
```

- [ ] **Step 2: For each file, replace all usages**

Read the file and replace every instance of:

```
{{ union_dataset_join_clause(left_alias="X", right_alias="Y") }}
```

with:

```
X._dbt_source_project = Y._dbt_source_project
```

Preserve the surrounding `and` keyword and indentation. The replacement is
mechanical — no judgment required.

**Example before:**

```sql
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gr") }}
```

**Example after:**

```sql
    and co._dbt_source_project = gr._dbt_source_project
```

- [ ] **Step 3: Also check `CLAUDE.md` in `src/dbt/kipptaf/`**

The CLAUDE.md file references the macro in its documentation section. This will
be updated in Task 12, but verify no SQL code blocks reference the old macro.

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "refactor: replace union_dataset_join_clause with _dbt_source_project joins (#3142)"
```

---

## Task 11: Validate with `dbt compile`

- [ ] **Step 1: Run dbt compile**

```bash
uv run dbt compile --project-dir src/dbt/kipptaf
```

Expected: no errors. If errors occur, they will be one of:

- **`union_dataset_join_clause` not found**: a downstream file was missed in
  Task 10. Search for remaining usages and replace.
- **`extract_code_location` not found**: a union model still references the old
  macro name. Should not happen (we renamed, not referenced it by name in SQL).
- **YAML contract error**: a contract-enforced model is missing
  `_dbt_source_project` in its properties YAML. Add it.
- **SQL syntax error**: a CTE wrap or column addition has a typo. Fix.

- [ ] **Step 2: Fix any errors and re-run until clean**

- [ ] **Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve dbt compile errors from _dbt_source_project refactor (#3142)"
```

---

## Task 12: Update documentation

**Files:**

- Modify: `src/dbt/kipptaf/CLAUDE.md`
- Modify: `docs/reference/dbt-conventions.md`

- [ ] **Step 1: Update `src/dbt/kipptaf/CLAUDE.md`**

Replace the section titled `### \`union_dataset_join_clause\` (critical)` (lines
~47-60) with:

````markdown
### `_dbt_source_project` column (critical)

Cross-district union models expose `_dbt_source_project`, extracted from
`_dbt_source_relation` via the `extract_source_project` macro in
`macros/utils.sql`. **Join on it directly** — never compare
`_dbt_source_relation` across tables:

```sql
inner join {{ ref("other_union_model") }} as b
    on a.id = b.id
    and a._dbt_source_project = b._dbt_source_project
```

When adding a new cross-district `union_relations` model, add the column:

```sql
select
    *,
    {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```
````

- [ ] **Step 2: Update `docs/reference/dbt-conventions.md`**

Replace the `union_dataset_join_clause()` bullet (lines 43-59) with:

````markdown
- **Join cross-district tables on `_dbt_source_project`** — all cross-district
  union models expose this column. Use it directly in join conditions:

  ```sql
  inner join {{ ref("other_union_model") }} as b
      on a.id = b.id
      and a._dbt_source_project = b._dbt_source_project
  ```

  When creating a new cross-district union model, add the column using the
  `extract_source_project` macro from `kipptaf/macros/utils.sql`:

  ```sql
  select
      *,
      {{ extract_source_project("union_relations") }}
          as _dbt_source_project,
  from union_relations
  ```
````

Update the `functions.region_join()` row in the BigQuery scalar functions table
(line 126) to note deprecation:

```markdown
| `functions.region_join(left_col, right_col)` | **Deprecated** — use
`a._dbt_source_project = b._dbt_source_project` instead |
```

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/CLAUDE.md docs/reference/dbt-conventions.md
git commit -m "docs: update dbt-conventions and kipptaf CLAUDE.md for _dbt_source_project (#3142)"
```

---

## Task 13: Final verification

- [ ] **Step 1: Verify no remaining references to old macros**

```bash
grep -r "union_dataset_join_clause\|extract_code_location" models/ macros/
```

Expected: no results.

- [ ] **Step 2: Run dbt compile one final time**

```bash
uv run dbt compile --project-dir src/dbt/kipptaf
```

Expected: clean compile, no errors.

- [ ] **Step 3: Spot-check a model**

Pick a powerschool staging model and a downstream tableau extract. Run:

```bash
uv run dbt show --project-dir src/dbt/kipptaf -s stg_powerschool__students --limit 5
```

Verify the output includes a `_dbt_source_project` column with values like
`kippnewark`, `kippcamden`, `kippmiami`, `kipppaterson`.
