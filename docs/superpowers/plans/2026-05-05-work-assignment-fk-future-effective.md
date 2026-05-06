# dim_staff_work_assignments latest-known grain — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reframe `dim_staff_work_assignments` to one row per `item_id` with the
latest-known worker-version's attributes, expose an `is_current` flag, and clear
the FK warnings on the work-assignment SCD2 children.

**Architecture:** Replace the `where is_current_record` filter on the parent
dim's source CTE with
`dbt_utils.deduplicate(... partition_by="item_id", order_by="effective_date_start desc")`.
Add a derived `is_current` boolean computed from `actual_start_date` and
`termination_date`. Audit direct consumers for hidden "row implies active today"
assumptions.

**Tech Stack:** dbt 1.11 / BigQuery / `dbt_utils.deduplicate` / kipptaf project.

**Spec:**
[docs/superpowers/specs/2026-05-05-work-assignment-fk-future-effective-design.md](../specs/2026-05-05-work-assignment-fk-future-effective-design.md)

**Issue:** [#3822](https://github.com/TEAMSchools/teamster/issues/3822)

---

## Worktree & path conventions

All work happens in the worktree
`.worktrees/cbini/fix/claude-work-assignment-fk-future-effective/`. Every shell
command must name it explicitly:

- `git -C .worktrees/cbini/fix/claude-work-assignment-fk-future-effective <args>`
- `uv run dbt <cmd> --project-dir .worktrees/cbini/fix/claude-work-assignment-fk-future-effective/src/dbt/kipptaf [...]`

`Edit` / `Read` / `Write` paths use absolute paths under the worktree.

`uv run dbt build` may need `--defer --state=target/prod/` if it depends on
unstaged externals. The state path is relative to `--project-dir`. The prod
manifest is refreshed by the `post-merge` hook on `git pull`; if missing,
regenerate first with
`uv run dbt parse --target prod --project-dir <project-dir> --target-path target/prod`.

---

## File Structure

| File                                                                                | Change                                                                      |
| ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_assignments.sql`            | Swap source-CTE filter for `dbt_utils.deduplicate`; add `is_current` column |
| `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_assignments.yml` | Update model description; add `is_current` column entry                     |
| `src/dbt/kipptaf/models/exposures/cube.yml`                                         | No change — `cube.yml` references the model, not its columns                |
| `src/dbt/kipptaf/models/marts/facts/fct_staff_attrition.sql`                        | Audit only — likely no change                                               |
| `src/dbt/kipptaf/models/marts/bridges/bridge_survey_expectations.sql`               | Audit only — likely no change                                               |
| `src/dbt/kipptaf/models/marts/facts/fct_work_assignment_compensation.sql`           | Audit only — already uses deduplicate by `item_id`; no change expected      |
| `src/dbt/kipptaf/models/marts/facts/fct_work_assignment_additional_earnings.sql`    | Audit only — pattern parallel to compensation; no change expected           |

The two SQL/YAML edits on the parent dim are the only required changes. Audit
tasks below are read-and-confirm — do not introduce filter changes unless an
actual "row implies active today" assumption is found.

---

## Task 1: Swap parent dim source filter

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_assignments.sql:1-30`

- [ ] **Step 1: Edit the `work_assignments` CTE**

Replace lines 2–30 (the entire `work_assignments as (...)` CTE) with the
deduplicate-based form. Use `Edit` with `old_string` matching the current CTE
and `new_string`:

```sql
    work_assignments as (
        {{
            dbt_utils.deduplicate(
                relation=ref(
                    "int_adp_workforce_now__workers__work_assignments"
                ),
                partition_by="item_id",
                order_by="effective_date_start desc",
            )
        }}
    ),
```

Note: this CTE now selects `*` from the intermediate via
`dbt_utils.deduplicate`. The downstream SELECT in this same model already
projects the columns it needs by name (`wa.associate_oid`, `wa.item_id`,
`wa.position_id`, etc.), so the column-narrowing previously done inside the CTE
is lost but harmless — the extra columns drop out at the final SELECT.

- [ ] **Step 2: Verify the file parses**

Run:
`uv run dbt parse --project-dir .worktrees/cbini/fix/claude-work-assignment-fk-future-effective/src/dbt/kipptaf --target dev`

Expected: parse succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git -C .worktrees/cbini/fix/claude-work-assignment-fk-future-effective add src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_assignments.sql
git -C .worktrees/cbini/fix/claude-work-assignment-fk-future-effective commit -m "refactor(dbt): dim_staff_work_assignments dedupe by item_id (#3822)"
```

---

## Task 2: Add `is_current` column to parent dim SELECT

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_assignments.sql`
  (final SELECT, after line 80)

- [ ] **Step 1: Insert `is_current` after `time_zone_code`**

Find the line ending `wa.worker_time_profile__time_zone_code as time_zone_code,`
and add `is_current` directly after it (before the `from` clause). Per the
src/dbt/CLAUDE.md SELECT-ordering rules (logicals come after column enumerations
and simple functions), this column lands at the bottom of the SELECT.

Use `Edit` to replace:

```sql
    wa.worker_time_profile__time_zone_code as time_zone_code,
from work_assignments as wa
```

with:

```sql
    wa.worker_time_profile__time_zone_code as time_zone_code,

    if(
        wa.actual_start_date <= current_date('{{ var("local_timezone") }}')
        and (
            wa.termination_date is null
            or wa.termination_date >= current_date('{{ var("local_timezone") }}')
        ),
        true,
        false
    ) as is_current,
from work_assignments as wa
```

- [ ] **Step 2: Verify the file parses**

Run:
`uv run dbt parse --project-dir .worktrees/cbini/fix/claude-work-assignment-fk-future-effective/src/dbt/kipptaf --target dev`

Expected: parse succeeds.

- [ ] **Step 3: Commit**

```bash
git -C .worktrees/cbini/fix/claude-work-assignment-fk-future-effective add src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_assignments.sql
git -C .worktrees/cbini/fix/claude-work-assignment-fk-future-effective commit -m "feat(dbt): add is_current to dim_staff_work_assignments (#3822)"
```

---

## Task 3: Update parent dim properties YAML

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_assignments.yml:2-13`
  (model description) and end of `columns:` (new column)

- [ ] **Step 1: Update model description**

Use `Edit` to replace the current `description: >-` block (lines 3–13) with:

```yaml
description: >-
  Staff work assignment dimension. One row per ADP work assignment (`item_id`),
  carrying the latest-known worker-version's attributes — includes currently
  active assignments, pending future hires, and historical/terminated
  assignments. Use the `is_current` boolean to filter to assignments active
  today. Contains stable, low-churn assignment-level scalars: position
  identifiers, flags, FTE, payroll fields, dates, pay cycle, standard hours,
  wage law coverage, and worker time profile. Employee number is resolved via
  LEFT JOIN to stg_people__employee_numbers (filtered to active number records),
  so staff_key and employee_number may be null for work assignments whose
  associate_oid has no active number mapping. High-churn attributes (assignment
  status, job title, worker type, location, org units, reports-to, compensation)
  are tracked in separate Type 2 child models that FK to this via
  work_assignment_key.
```

- [ ] **Step 2: Add `is_current` column entry**

Append a new column entry after `time_zone_code` (after the file's last existing
column, around line 180). Use `Edit` to replace:

```yaml
- name: time_zone_code
  data_type: string
  description: >-
    IANA time zone code for this work assignment's time-and-attendance clock.
```

with:

```yaml
- name: time_zone_code
  data_type: string
  description: >-
    IANA time zone code for this work assignment's time-and-attendance clock.

- name: is_current
  data_type: boolean
  description: >-
    TRUE when today falls within this work assignment's actual_start_date
    through termination_date range (termination_date NULL is treated as
    open-ended). FALSE for pending future hires and ended assignments. Use this
    flag to filter the dim to today's active assignments; leave unfiltered to
    include pending and historical rows.
```

- [ ] **Step 3: Re-parse with no partial parse**

Per src/dbt/CLAUDE.md ("Singular-test description placement"), property changes
sometimes need a fresh parse:

Run:
`uv run dbt parse --no-partial-parse --project-dir .worktrees/cbini/fix/claude-work-assignment-fk-future-effective/src/dbt/kipptaf --target dev`

Expected: parse succeeds with no contract violations.

- [ ] **Step 4: Commit**

```bash
git -C .worktrees/cbini/fix/claude-work-assignment-fk-future-effective add src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_assignments.yml
git -C .worktrees/cbini/fix/claude-work-assignment-fk-future-effective commit -m "docs(dbt): document is_current and latest-known grain on dim_staff_work_assignments (#3822)"
```

---

## Task 4: Build the parent and verify FK warnings clear

**Files:**

- Read: dbt run output

- [ ] **Step 1: Refresh prod manifest if needed**

If `src/dbt/kipptaf/target/prod/manifest.json` is missing or stale, regenerate:

```bash
uv run dbt parse --target prod --project-dir .worktrees/cbini/fix/claude-work-assignment-fk-future-effective/src/dbt/kipptaf --target-path target/prod
```

- [ ] **Step 2: Build the parent dim and its descendants**

```bash
uv run dbt build \
  --select dim_staff_work_assignments+ \
  --project-dir .worktrees/cbini/fix/claude-work-assignment-fk-future-effective/src/dbt/kipptaf \
  --target dev \
  --defer --state=target/prod/
```

Expected:

- `dim_staff_work_assignments` builds without uniqueness or contract failures.
- Children `dim_work_assignment_organizational_units` and
  `dim_work_assignment_locations` build.
- The two `relationships` tests on `work_assignment_key`
  (`...organizational_units` and `...locations`) report PASS, not WARN.
  Specifically: no `Got 4 results, configured to warn if != 0` and no
  `Got 2 results, configured to warn if != 0`.

If a relationships warning persists, before assuming the design is wrong, follow
src/dbt/CLAUDE.md "Stale dev tables shadow `--defer`" — clone the parent from
prod first:
`uv run dbt clone --select dim_staff_work_assignments --project-dir .worktrees/.../src/dbt/kipptaf --target dev`,
then re-run the build.

- [ ] **Step 3: Spot-check the previously-orphaned item_ids appear**

Use BigQuery MCP (or any SQL runner) against the dev schema for the current user
— substitute `<user>_marts` for the actual dev schema name. The orphan keys live
at the bottom of the dim now; they should appear with `is_current = false`
(today is before their actual_start_date).

```sql
select
  work_assignment_key,
  hire_date,
  actual_start_date,
  termination_date,
  is_current,
from `teamster-332318.<user>_kipptaf_marts.dim_staff_work_assignments`
where work_assignment_key in (
  'a461083cdd17ad4966ab24c85f8719ee',
  'fc618241090090641e9a4111eb06af3c'
)
```

Expected: two rows, both with `is_current = false` and `actual_start_date` in
2026-05-11 / 2026-05-18.

- [ ] **Step 4: No commit yet** — proceed to audit tasks before committing the
      verification result.

---

## Task 5: Audit `fct_staff_attrition`

**Files:**

- Read: `src/dbt/kipptaf/models/marts/facts/fct_staff_attrition.sql`

- [ ] **Step 1: Confirm join semantics**

Read the file and confirm that `dim_staff_work_assignments` is joined inner
solely to resolve `work_assignment_key → staff_key`. The cohort logic is
anchored by `dim_work_assignment_status` (`status_code = 'A'`/`'T'`) within
academic-year date windows. The fact does not assume "every row in the dim is
active today."

Expected finding: no change required. Pending future hires won't enter cohorts
until their status row turns 'A' inside the window; terminated rows exit via
`status_code = 'T'`.

- [ ] **Step 2: Document the audit conclusion**

If no change: skip to Task 6. If a real "row implies active today" assumption is
found, surface it to the user before editing — the reporting-value principle
from the spec means filters that would _suppress_ pending/historical rows must
not be silently added.

---

## Task 6: Audit `bridge_survey_expectations`

**Files:**

- Read: `src/dbt/kipptaf/models/marts/bridges/bridge_survey_expectations.sql`

- [ ] **Step 1: Confirm join semantics**

The `staff` cohort joins `dim_work_assignment_status` filtered to
`status_code = 'A'` within `effective_start_date`/`effective_end_date` spanning
`sa.response_deadline_date`, then joins `dim_work_assignment_primary` similarly,
then resolves `dim_staff_work_assignments` by `work_assignment_key` to get
`staff_key`.

Expected finding: no change required. The deadline-date window naturally
excludes pending future assignments whose status row hasn't activated by the
deadline. Adding pending/historical rows to the parent dim cannot leak through
the date-bounded inner joins on the SCD2 children.

- [ ] **Step 2: Document the audit conclusion**

If no change: skip to Task 7.

---

## Task 7: Audit `fct_work_assignment_compensation` and `fct_work_assignment_additional_earnings`

**Files:**

- Read:
  `src/dbt/kipptaf/models/marts/facts/fct_work_assignment_compensation.sql`
- Read:
  `src/dbt/kipptaf/models/marts/facts/fct_work_assignment_additional_earnings.sql`

- [ ] **Step 1: Confirm both already use `dbt_utils.deduplicate` keyed by
      `item_id`**

Both compensation and additional-earnings facts emit `work_assignment_key`
hashed from `item_id`. The compensation fact already deduplicates the
intermediate by `item_id, base_remuneration__effective_date` and builds SCD2 on
its own effective dates — independent of worker-version currency. The
relationship to `dim_staff_work_assignments` is FK only; expanding the parent's
grain to all known item*ids strictly \_reduces* potential orphans for these
facts.

Expected finding: no change required.

- [ ] **Step 2: Document the audit conclusion**

If no change: skip to Task 8.

---

## Task 8: Confirm `dim_staff` and `cube.yml` references are descriptive only

**Files:**

- Read: `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff.yml`
- Read: `src/dbt/kipptaf/models/exposures/cube.yml`

- [ ] **Step 1: Verify `dim_staff.yml` mention is descriptive text**

The mention is in a `description:` paragraph noting that
`dim_staff_work_assignments` FKs to `dim_staff`. No code dependency.

Expected finding: no change required.

- [ ] **Step 2: Verify `cube.yml` lists the model in `depends_on`**

Run: `Grep` for `dim_staff_work_assignments` in
`src/dbt/kipptaf/models/exposures/cube.yml`.

Expected: a `- ref("dim_staff_work_assignments")` line under `depends_on`.

The Cube semantic-layer schema files live outside this dbt project (Cube YAML is
consumed by the Cube service, not dbt). Surfacing `is_current` to BI consumers
is a follow-up tracked separately — not in this PR's scope.

- [ ] **Step 3: No commit** — audit tasks are read-only.

---

## Task 9: Pre-merge checklist

**Files:**

- Read: model files touched in Tasks 1–3

- [ ] **Step 1: Diamond-path scan**

The change adds no new FK columns to any fact or child dim — only an
`is_current` boolean on the parent. No new traversal paths. No diamond risk.

- [ ] **Step 2: Column-naming rubric (R1–R10) check on `is_current`**

- R1 (no source-system prefix): pass.
- R2 (no KIPP-specific language): pass.
- R3 (`is_` prefix on boolean): pass.
- R4 (date suffix): N/A — boolean.
- R8 (no plumbing): pass.
- R10 (entity qualification): unqualified is correct — no same-name-collision
  risk on the dim's surface.

- [ ] **Step 3: Project board scan**

Visit
[Data Team project board](https://github.com/orgs/TEAMSchools/projects/4/views/1)
and grep for any open issues mentioning `dim_staff_work_assignments`,
`work_assignment_key`, or "future-dated work assignment." If any are
incidentally resolved, list them in the PR body so they can be closed alongside
the merge.

- [ ] **Step 4: Push the branch**

```bash
git -C .worktrees/cbini/fix/claude-work-assignment-fk-future-effective push -u origin cbini/fix/claude-work-assignment-fk-future-effective
```

- [ ] **Step 5: Open the PR**

Use `mcp__github__create_pull_request` with the body sourced from
`.github/pull_request_template.md`. Title:
`fix(dbt): dim_staff_work_assignments includes pending future hires (#3822)`.

PR body must reference the spec, list the audit findings (Tasks 5–8 each "no
change required"), and include the pre-merge checklist completion state.

---

## Out of Scope (do not implement here)

- Promoting `dim_staff_work_assignments` to SCD Type 2.
- Restructuring `int_adp_workforce_now__workers__work_assignments`.
- Adding withdrawn-assignment data-quality monitoring.
- Surfacing `is_current` in Cube semantic layer YAML — follow-up issue.
