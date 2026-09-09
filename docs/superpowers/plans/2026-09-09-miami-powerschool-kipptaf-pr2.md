# Miami PowerSchool Retirement, PR 2 (kipptaf) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make kipptaf read the rebuilt Miami PowerSchool archive as-is: drop
the 9 Miami relations no consumer wants, replace the 7 kipptaf copies of the
moved models with union wrappers over the package, delete the Miami-only
renumber and cutover steps the archive now carries, repoint 3 readers whose join
keys the rebuild broke, and tag PII on the moved package models.

**Architecture:** Every kipptaf PowerSchool model is a
`dbt_utils.union_relations` wrapper over per-region `source()` tables plus
`_dbt_source_project`. This PR changes which regions each wrapper lists and
removes two kinds of Miami-only code from the students layer: the
`focus_student_number` offset (the archive is already 8400-prefixed) and the
`not (kippmiami and year >= cutover)` predicate on PowerSchool branches (the
archive ends at AY2025). The Focus-side floor
`where academic_year >= focus_start_academic_year` stays everywhere; only the
PowerSchool-side exclusion goes.

**Tech Stack:** dbt on BigQuery via `uv run dbt`, the BigQuery MCP for read-only
checks, trunk for lint.

Spec:
`docs/superpowers/specs/2026-09-08-miami-powerschool-retirement-design.md`,
section "kipptaf changes (PR 2)" (revised 2026-09-09) and "Verdicts for readers
of a dropped relation". Issue: #5197.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-kipptaf-pr2`.
  Every path below is relative to it. Every git call is `git -C <worktree>`.
- Never bare `dbt`. Always
  `uv run dbt <cmd> --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-kipptaf-pr2/src/dbt/kipptaf --profiles-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-kipptaf-pr2/src/dbt/kipptaf`.
  Below, `KIPPTAF` stands for that `--project-dir ... --profiles-dir ...` pair.
- Run `uv run dbt deps KIPPTAF` once before the first parse in the worktree.
- Validation is compile-and-query, not dev build.
  `uv run dbt compile --target prod --select <model> KIPPTAF` writes
  `src/dbt/kipptaf/target/compiled/kipptaf/models/.../<model>.sql` with every
  ref resolved to prod. Wrap that SQL in `select count(*) from (...)` and run it
  through the BigQuery MCP. Compile is read-only; it never writes to prod. Under
  `--target prod` the kipptaf `sources-kipp*` resolve to the real
  `kipp<region>_powerschool` datasets.
- Column-resolution gate before push:
  `uv run dbt build --empty --select state:modified+ --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod KIPPTAF`.
  `--state` is the MAIN checkout's prod manifest, absolute path. `--empty`
  leaves the selected dev relations at 0 rows; that is expected, do not read it
  as data loss.
- Never emit student-level values anywhere outside the terminal. Row counts and
  distinct-key counts are fine.
- Warehouse `DELETE` goes to the user's terminal (Task 2). Never run it from a
  tool.
- Lint before push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree. `trunk fmt <files>` first when it reports
  formatting.
- Commit messages: conventional commits, `Refs #5197`, and the trailer
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Write the message
  to `/workspaces/teamster/.claude/scratch/commit-msg.txt` and commit with `-F`.

## Two prod regressions PR 1 left behind

The rebuild changed two things in the archive that kipptaf did not expect. Both
are live in prod today and both are fixed by tasks in this plan. If the user
wants either fixed sooner, Task 2 and Task 7 stand alone.

1. `kippmiami_powerschool.stg_powerschool__students.student_number` is now
   8400-prefixed on all 3,946 rows. `rpt_gsheets__kippfwd_miami_roster` joins it
   on the bare `int_focus__students.powerschool_id`, so its ADA, cumulative GPA,
   `gpa_y1`, advisor, and IEP columns read null for every PowerSchool-era year.
   Task 7 fixes the join.
2. `stg_powerschool__calendar_day` was not among the 14 bounded tables, and
   `stg_powerschool__terms` lost its AY2026 scaffold rows. 1,092 Miami
   `calendar_day` rows dated 2026-07-01 or later now have no covering term, so
   `int_students__calendar_day` keeps them as PowerSchool rows with a null
   `academic_year` (1,210 null-year Miami rows total; 118 of those are
   historical no-term days that were always kept). Task 2 bounds the archive
   table; Task 6 then deletes the predicate that used to catch them.

---

### Task 1: Snapshot prod baselines

**Files:**

- Create: `/workspaces/teamster/.claude/scratch/pr2-baseline.md` (scratch, not
  committed)

**Interfaces:**

- Produces: a table of `model, academic_year, miami_rows` that Task 9 compares
  against.

- [ ] **Step 1: Run the baseline query through the BigQuery MCP**

One query per model. The models are the 7 verdict readers of a dropped relation
plus the 3 repoint targets plus `int_students__calendar_day`. Substitute each
`<dataset>.<model>` pair from the list below.

```sql
select academic_year, count(*) as miami_rows
from `teamster-332318.<dataset>.<model>`
where _dbt_source_project = 'kippmiami'
group by 1
order by 1
```

| dataset             | model                                              |
| ------------------- | -------------------------------------------------- |
| kipptaf_powerschool | int_powerschool__log                               |
| kipptaf_powerschool | int_powerschool__state_assessments_transfer_scores |
| kipptaf_deanslist   | rpt_deanslist__designations                        |
| kipptaf_deanslist   | rpt_deanslist__hs_transcript_programs              |
| kipptaf_powerschool | rpt_powerschool__autocomm_students                 |
| kipptaf_powerschool | rpt_powerschool__autocomm_teachers                 |
| kipptaf_extracts    | int_extracts__student_enrollments_subjects         |
| kipptaf_students    | int_students__calendar_day                         |

Some of these have no `academic_year` or no `_dbt_source_project`. When the
query errors on a missing column, drop the missing column and record `count(*)`
only. Record the verdict models' Miami totals even when they are already 0.

For the 3 repoint models, record `count(*)` and one aggregate each:

```sql
-- rpt_gsheets__kippfwd_miami_roster: how many rows have any PowerSchool-era value
select academic_year, count(*) as rows_, countif(previous_year_ada is not null) as with_ada,
  countif(gpa_cumulative is not null) as with_gpa
from `teamster-332318.kipptaf_extracts.rpt_gsheets__kippfwd_miami_roster`
group by 1 order by 1
```

```sql
-- rpt_gsheets__kippmiami_payout_roster: rows per year
select academic_year, count(*) as rows_
from `teamster-332318.kipptaf_extracts.rpt_gsheets__kippmiami_payout_roster`
group by 1 order by 1
```

```sql
-- rpt_deanslist__state_test_scores: FAST rows and distinct students
select academic_year_int, count(*) as rows_, count(distinct student_number) as students
from `teamster-332318.kipptaf_extracts.rpt_deanslist__state_test_scores`
where test_type = 'FAST'
group by 1 order by 1
```

If a dataset name is wrong, find it with
`select table_schema from teamster-332318.INFORMATION_SCHEMA.TABLES where table_name = '<model>'`
(region-qualified `region-us` if the bare form errors).

- [ ] **Step 2: Write the results to the scratch file**

Paste each result as a markdown table under a heading naming the model. This
file is the "before" side of Task 9.

---

### Task 2: Bound the archive's `calendar_day` (user's terminal) and record the 16th hook

**Files:**

- Modify: `src/dbt/kippmiami/CLAUDE.md` (the PowerSchool paragraph, lines 15-24)

**Interfaces:**

- Produces: `kippmiami_powerschool.stg_powerschool__calendar_day` with no row
  dated 2026-07-01 or later. Task 6 depends on it.

- [ ] **Step 1: Confirm the row count to delete**

Run through the BigQuery MCP:

```sql
select count(*) as to_delete, min(date_value) as first_date, max(date_value) as last_date
from `teamster-332318.kippmiami_powerschool.stg_powerschool__calendar_day`
where date_value >= '2026-07-01'
```

Expected: `to_delete` = 1092, `last_date` = 2027-06-29. If the count differs,
stop and report before handing off the delete.

- [ ] **Step 2: Hand the delete to the user**

Post this statement in chat and ask the user to run it in their terminal. Do not
run it from any tool.

```sql
delete from `teamster-332318.kippmiami_powerschool.stg_powerschool__calendar_day`
where date_value >= '2026-07-01'
```

- [ ] **Step 3: Verify after the user confirms**

Re-run the Step 1 query. Expected: `to_delete` = 0.

- [ ] **Step 4: Record the hook in the rebuild recipe note**

In `src/dbt/kippmiami/CLAUDE.md`, the PowerSchool paragraph ends with "the
`dbt_project.yml` hook YAML in #5201 is the rebuild recipe." Append this
sentence to that paragraph:

```markdown
A 16th hook belongs in that recipe:
`stg_powerschool__calendar_day: +post-hook: delete from {{ this }} where date_value >= '2026-07-01'`.
The 2026-09-09 rebuild missed it and the rows were deleted by hand (#5197).
```

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-kipptaf-pr2
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kippmiami/CLAUDE.md </dev/null
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-kipptaf-pr2 add -u
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-kipptaf-pr2 commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt
```

Commit message:
`docs(kippmiami): record the calendar_day bound the archive rebuild recipe needs`

---

### Task 3: Drop the 9 Miami relations and 13 source entries

**Files:**

- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__users.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__userscorefields.sql`
- Modify: `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__log.sql`
- Modify: `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__gen.sql`
- Modify: `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__fte.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__spenrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__student_enrollment_union.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__district_entry_date.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__teacher_grade_levels.sql`

**Interfaces:**

- Produces: 9 unions with 3 relations each. `sources-kippmiami.yml` with 13
  fewer tables and a new description.

- [ ] **Step 1: Remove the `kippmiami_powerschool` relation from the 9 unions**

Each file has a `relations=[ ... ]` list with 4 `source(...)` calls. Delete the
one whose first argument is `"kippmiami_powerschool"`. Two shapes appear. Short
form (users, log, gen, fte):

```sql
                    source("kippmiami_powerschool", "stg_powerschool__users"),
```

Wrapped form (userscorefields, spenrollments, student_enrollment_union,
district_entry_date, teacher_grade_levels), 3 or 4 lines:

```sql
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__district_entry_date",
                    ),
```

Delete the whole `source(...)` call including its trailing comma. Leave the
other 3 relations and the rest of the file unchanged.

- [ ] **Step 2: Verify with grep**

```bash
grep -c kippmiami \
  src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__{users,userscorefields,log,gen,fte}.sql \
  src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__{spenrollments,student_enrollment_union,district_entry_date,teacher_grade_levels}.sql
```

Expected: every line ends in `:0`.

- [ ] **Step 3: Remove 13 table entries from `sources-kippmiami.yml`**

Each entry is 9 lines: `- name: <table>` then a `config: meta: dagster:` block
with `group` and a 3-item `asset_key` list. Delete the full entry for each of:

```text
stg_powerschool__fte
stg_powerschool__gen
stg_powerschool__log
stg_powerschool__period
stg_powerschool__studentrace
stg_powerschool__u_def_ext_students
stg_powerschool__users
stg_powerschool__userscorefields
stg_powerschool__sced_code_mapping
int_powerschool__spenrollments
int_powerschool__student_enrollment_union
int_powerschool__teacher_grade_levels
int_powerschool__district_entry_date
```

Use a script so no neighbor entry is clipped. Write it to
`/workspaces/teamster/.claude/scratch/drop_miami_sources.py` and run it by
absolute path:

```python
import pathlib, re

p = pathlib.Path(
    "/workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-kipptaf-pr2"
    "/src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml"
)
drop = {
    "stg_powerschool__fte", "stg_powerschool__gen", "stg_powerschool__log",
    "stg_powerschool__period", "stg_powerschool__studentrace",
    "stg_powerschool__u_def_ext_students", "stg_powerschool__users",
    "stg_powerschool__userscorefields", "stg_powerschool__sced_code_mapping",
    "int_powerschool__spenrollments", "int_powerschool__student_enrollment_union",
    "int_powerschool__teacher_grade_levels", "int_powerschool__district_entry_date",
}
text = p.read_text()
head, sep, body = text.partition("    tables:\n")
entries = re.split(r"(?m)^(?=      - name: )", body)
kept, removed = [], []
for e in entries:
    m = re.match(r"      - name: (\S+)", e)
    (removed if m and m.group(1) in drop else kept).append(e)
assert len(removed) == 13, [re.match(r"      - name: (\S+)", e).group(1) for e in removed]
p.write_text(head + sep + "".join(kept))
print("removed", len(removed), "kept", sum(1 for e in kept if e.startswith("      - name:")))
```

Expected output: `removed 13 kept 76`.

- [ ] **Step 4: Replace the source description**

In the same file, the `description: >-` block under
`- name: kippmiami_powerschool` reads "Frozen pre-Focus PowerSchool archive
(final ODBC pull 2026-07-01; Miami's SIS moved to Focus). Never rebuilt — ...".
Replace the whole block with:

```yaml
description: >-
  Frozen pre-Focus PowerSchool archive (final ODBC pull 2026-07-01; Miami's SIS
  moved to Focus). Rebuilt once on 2026-09-09 from the frozen externals with the
  8400 Focus prefix on student_number and an AY2025 bound applied (#5012). The
  dataset must not be dropped. Declared BQ-native (plain schema, no target
  branch) so every target reads the prod tables directly.
```

- [ ] **Step 5: Parse and check the 9 models compile**

```bash
uv run dbt deps KIPPTAF
uv run dbt parse --target prod KIPPTAF
uv run dbt compile --target prod KIPPTAF --select stg_powerschool__users stg_powerschool__userscorefields stg_powerschool__log stg_powerschool__gen stg_powerschool__fte int_powerschool__spenrollments int_powerschool__student_enrollment_union int_powerschool__district_entry_date int_powerschool__teacher_grade_levels
grep -c kippmiami_powerschool src/dbt/kipptaf/target/compiled/kipptaf/models/powerschool/staging/stg_powerschool__users.sql
```

Expected: parse succeeds, compile succeeds, the grep prints `0`.

- [ ] **Step 6: Lint and commit**

Run trunk on the 10 files. Commit message:
`refactor(kipptaf): drop the Miami relation from 9 PowerSchool unions and 13 stale source entries`

---

### Task 4: Replace the 7 kipptaf copies with wrappers over the package models

**Files:**

- Rewrite:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__final_grades_rollup.sql`
- Rewrite:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_term_current.sql`
- Rewrite:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_term_pivot.sql`
- Rewrite:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__log.sql`
- Rewrite:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__s_nj_stu_x_unpivot.sql`
- Rewrite:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpnode.sql`
- Rewrite:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpprogress_grades.sql`
- Modify: the 7 matching `properties/int_powerschool__<name>.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml`,
  `sources-kippcamden.yml`, `sources-kipppaterson.yml`, `sources-kippmiami.yml`

**Interfaces:**

- Consumes: the package models materialized in each region's
  `kipp<region>_powerschool` dataset (PR 1, verified 2026-09-09).
- Produces: 7 wrappers with the same column set as before plus
  `_dbt_source_relation` and `_dbt_source_project`. Consumers keep `ref()`.

- [ ] **Step 1: Confirm the package tables exist per region**

Through the BigQuery MCP, one query:

```sql
select table_schema, table_name
from `teamster-332318.region-us`.INFORMATION_SCHEMA.TABLES
where table_name in (
  'int_powerschool__final_grades_rollup', 'int_powerschool__gpa_term_current',
  'int_powerschool__gpa_term_pivot', 'int_powerschool__log',
  'int_powerschool__s_nj_stu_x_unpivot', 'int_powerschool__gpnode',
  'int_powerschool__gpprogress_grades')
  and table_schema in ('kippnewark_powerschool', 'kippcamden_powerschool',
    'kipppaterson_powerschool', 'kippmiami_powerschool')
order by 1, 2
```

Expected: Newark and Camden list all 7. Paterson lists 5 (no `gpnode`, no
`gpprogress_grades`). Miami lists `final_grades_rollup`, `gpa_term_pivot`, and
`gpa_term_current` only if the package materializes it as a table there;
`gpa_term_current` is `materialized: ephemeral` in the package, so expect it to
be MISSING in every region. If it is missing everywhere, the `gpa_term_current`
wrapper cannot read a source table. Handle it in Step 2.

- [ ] **Step 2: Write the 7 wrapper SQL files**

Every wrapper has this shape. `RELATIONS` is the per-model list below.

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    RELATIONS
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

Relations per model. Use `model.name` so the file cannot drift from the table
name.

| model                                  | relations                                                                                                                                                                                  |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `int_powerschool__final_grades_rollup` | `source("kippnewark_powerschool", model.name), source("kippcamden_powerschool", model.name), source("kippmiami_powerschool", model.name), source("kipppaterson_powerschool", model.name),` |
| `int_powerschool__gpa_term_pivot`      | same 4 as above                                                                                                                                                                            |
| `int_powerschool__log`                 | `source("kippnewark_powerschool", model.name), source("kippcamden_powerschool", model.name), source("kipppaterson_powerschool", model.name),`                                              |
| `int_powerschool__s_nj_stu_x_unpivot`  | same 3 NJ as `log`                                                                                                                                                                         |
| `int_powerschool__gpnode`              | `source("kippnewark_powerschool", model.name), source("kippcamden_powerschool", model.name),`                                                                                              |
| `int_powerschool__gpprogress_grades`   | same 2 as `gpnode`                                                                                                                                                                         |

`int_powerschool__gpa_term_current` is ephemeral in the package, so there is no
table to wrap. Keep the kipptaf model as a 2-line filter over the kipptaf
`gpa_term` wrapper, which is what it already is:

```sql
select *,
from {{ ref("int_powerschool__gpa_term") }}
where is_current
```

That drops the explicit column list the current file carries; `select *` on a
wrapper is the repo convention (see `int_powerschool__gpa_term_pivot` before
this task). It also keeps `_dbt_source_relation` and `_dbt_source_project`,
which the current column list omits.

- [ ] **Step 3: Rewrite the 6 wrapper YAML files**

For each of the 6 wrapped models (not `gpa_term_current`), replace the
`description` and `columns` so the file documents the wrapper, not the logic.
Keep the existing `data_tests` block as is: each already leads its
`combination_of_columns` with `_dbt_source_relation` or `_dbt_source_project`.
The `final_grades_rollup` test leads with `_dbt_source_project`; leave it. Model
the text on `properties/int_powerschool__state_assessments_transfer_scores.yml`:

```yaml
models:
  - name: int_powerschool__<name>
    description: >-
      Union of each region's int_powerschool__<name> (the powerschool package
      model). Column docs and the per-instance tests live in the package; this
      wrapper adds _dbt_source_project so studentid, which is only unique within
      one PowerSchool instance, can be disambiguated downstream. <REGION NOTE>
    data_tests: <unchanged>
    columns:
      - name: _dbt_source_relation
        data_type: string
        description: Source relation identifier from dbt_utils.union_relations.

      - name: _dbt_source_project
        data_type: string
        description: >-
          District code location derived from _dbt_source_relation. Needed to
          disambiguate studentid, which is only unique within a single
          PowerSchool instance.
```

`<REGION NOTE>` per model:

- `final_grades_rollup`, `gpa_term_pivot`: "Includes the frozen Miami archive
  (AY2025 and earlier)."
- `log`, `s_nj_stu_x_unpivot`: "NJ only; Miami's PowerSchool history for this
  table ends at AY2025 and nothing reports it."
- `gpnode`, `gpprogress_grades`: "Newark and Camden only; Paterson disables the
  grad-plan tables and Miami never had them."

For `gpa_term_pivot` the current YAML has `config: materialized: table`; keep
it. For `s_nj_stu_x_unpivot` likewise. Delete every other column entry: the
package YAML documents them.

- [ ] **Step 4: Add source table entries in the region files**

In `sources-kippnewark.yml`, `sources-kippcamden.yml`, and
`sources-kipppaterson.yml`, find the entry
`- name: int_powerschool__state_assessments_transfer_scores` (line 665 in all
three today) and insert new entries directly after its 9 lines. Each entry:

```yaml
- name: int_powerschool__<name>
  config:
    meta:
      dagster:
        group: powerschool
        asset_key:
          - <region>
          - powerschool
          - int_powerschool__<name>
```

Names per file:

- Newark and Camden, 6 entries each: `final_grades_rollup`, `gpa_term_pivot`,
  `log`, `s_nj_stu_x_unpivot`, `gpnode`, `gpprogress_grades`
- Paterson, 4 entries: `final_grades_rollup`, `gpa_term_pivot`, `log`,
  `s_nj_stu_x_unpivot`
- `sources-kippmiami.yml`, 2 entries appended at the end of `tables:`, with
  `asset_key` first item `kippmiami`: `final_grades_rollup`, `gpa_term_pivot`

Write these with a script too, asserting the anchor matches exactly once per
file.

- [ ] **Step 5: Compile and count**

```bash
uv run dbt parse --target prod KIPPTAF
uv run dbt compile --target prod KIPPTAF --select int_powerschool__final_grades_rollup int_powerschool__gpa_term_pivot int_powerschool__log int_powerschool__s_nj_stu_x_unpivot int_powerschool__gpnode int_powerschool__gpprogress_grades int_powerschool__gpa_term_current
```

For each of the 6 wrappers, run the compiled SQL through the BigQuery MCP as
`select _dbt_source_project, count(*) as n from (<compiled sql>) group by 1 order by 1`
and compare with the same query against the current prod table
`teamster-332318.kipptaf_powerschool.int_powerschool__<name>`. Expected: NJ
counts equal per project. For `final_grades_rollup` and `gpa_term_pivot`,
`kippmiami` should also be present in both and equal. For the other 4,
`kippmiami` is absent from the new result; record the prod Miami count that
disappears (the spec's verdict says nothing reads it).

If `gpa_term_pivot` or `final_grades_rollup` differ for NJ, stop: the package
model and the kipptaf copy diverged after PR 1. Report the delta.

- [ ] **Step 6: Lint and commit**

Commit message:
`refactor(kipptaf): wrap the 7 moved PowerSchool intermediates over the package models`

---

### Task 5: Delete the 3 `focus_student_number` calls

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__ada.sql:24-27`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__attendance_streak.sql:33-36`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__ps_adaadm_daily_ctod.sql:41-44`
- Modify: the 3 matching `properties/*.yml` `student_number` descriptions

**Interfaces:**

- Produces: the 3 wrappers select `*` from their union; Miami `student_number`
  is already prefixed by the archive.

- [ ] **Step 1: Replace the select list in each of the 3 files**

Each file ends with this block (alias `unioned`):

```sql
select
    * except (student_number),

    {{ focus_student_number("student_number", "yearid + 1990", "_dbt_source_project") }}
    as student_number,
from unioned
```

Replace with:

```sql
select *,
from unioned
```

If the file's final select carries other expressions besides the macro, keep
those and remove only the `except (student_number)` and the macro line.

- [ ] **Step 2: Update the 3 YAML descriptions**

Each `properties/int_powerschool__<name>.yml` has a `student_number` column
whose description says the archive "carries the bare pre-Focus number, so those
rows are offset by 8400000000". Replace that description with:

```yaml
description:
  Network student number. Miami's frozen PowerSchool archive was rebuilt with
  the 8400 Focus prefix applied (#5012), so every project's rows share one id
  space with no offset here.
```

- [ ] **Step 3: Verify the macro has no remaining PowerSchool callers**

```bash
grep -rl "focus_student_number" src/dbt/kipptaf/models
```

Expected: 7 files, none under `models/powerschool/`. Leave the macro in
`src/dbt/kipptaf/macros/utils.sql`; the vendor-file callers are out of scope.

- [ ] **Step 4: Compile and check the prefix**

```bash
uv run dbt compile --target prod KIPPTAF --select int_powerschool__ada int_powerschool__attendance_streak int_powerschool__ps_adaadm_daily_ctod
```

Run each compiled SQL through the BigQuery MCP as
`select countif(student_number < 8400000000) as bare, count(*) as n from (<compiled sql>) where _dbt_source_project = 'kippmiami'`.
Expected: `bare` = 0 for all 3, and `n` equal to the same query on the prod
table.

- [ ] **Step 5: Lint and commit**

Commit message:
`refactor(kipptaf): drop the Miami student_number offset the archive now carries`

---

### Task 6: Delete the PowerSchool-side cutover predicate in 8 students models

**Files:**

- Modify: `src/dbt/kipptaf/models/students/intermediate/int_students__ada.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__attendance_daily.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__attendance_streak.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__calendar_day.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__calendar_rollup.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__calendar_week.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__final_grades.sql`
- Modify: `src/dbt/kipptaf/models/students/intermediate/int_students__gpa.sql`

**Interfaces:**

- Consumes: Task 2 done (no Miami `calendar_day` row after 2026-06-30).
- Produces: each PowerSchool CTE selects every archive row. The Focus-side floor
  (`where <focus>.academic_year >= c.focus_start_academic_year`) stays in every
  file. The `cutover` or `sis_cutover` CTE stays because the Focus side still
  reads it.

- [ ] **Step 1: Delete the PowerSchool-side predicate in 7 files**

In `ada`, `attendance_streak`, `calendar_rollup`, `calendar_week`, and
`attendance_daily`, the PowerSchool CTE ends with:

```sql
        cross join cutover as c
        where
            not (
                <alias>._dbt_source_project = 'kippmiami'
                and <alias>.yearid >= c.focus_start_academic_year - 1990
            )
    ),
```

Delete the `cross join cutover as c` line and the whole `where not (...)`
clause, so the CTE ends at its `from` (or its last `left join`) followed by
`    ),`. In `attendance_daily` the CTE has a `left join focus_stints` before
the `where`; keep the join, delete the `cross join` and the `where`.

In `final_grades`, the block is:

```sql
        cross join sis_cutover as sc
        -- left, not inner: ...
        left join
            powerschool_students as ps
            on fg.studentid = ps.studentid
            and fg._dbt_source_project = ps._dbt_source_project
        where
            not (
                fg._dbt_source_project = 'kippmiami'
                and fg.academic_year >= sc.focus_start_academic_year
            )
    ),
```

Delete `cross join sis_cutover as sc` and the `where not (...)` clause. Keep the
comment and the `left join`.

In `gpa`, the same shape with `gt.yearid >= sc.focus_start_yearid`. Delete the
`cross join sis_cutover as sc` line and the `where not (...)` clause. Then in
the `sis_cutover` CTE at the top, delete the `focus_start_yearid` expression and
its 3-line comment (nothing reads it after this step); keep
`focus_start_academic_year`.

Also update each file's CTE comment. The lines "The frozen PowerSchool archive
keeps serving Miami for every year Focus does not cover. Scoping by year rather
than by project is what preserves Miami AY2020 through AY2025." become:

```sql
    -- The frozen PowerSchool archive ends at AY2025 (rebuilt with that bound,
    -- #5012), so every archive row is a pre-Focus year and needs no cutover
    -- predicate. The Focus branch below still floors at the cutover year.
```

- [ ] **Step 2: Delete the flag and its filter in `calendar_day`**

In `int_students__calendar_day.sql`:

1. Delete the `is_focus_covered_year` expression (the
   `coalesce(t.yearid >= c.focus_start_academic_year - 1990, false) as is_focus_covered_year,`
   lines and their 3-line comment) from the `powerschool_dated` select list.
2. Delete `cross join cutover as c` from `powerschool_dated` if present.
3. Change the `powerschool_conformed` filter
   `where not (_dbt_source_project = 'kippmiami' and is_focus_covered_year)` to
   nothing: delete the `where` line.
4. Update the comment above `powerschool_conformed` that ends "A no-term day is
   never dropped here, even for Miami — see `is_focus_covered_year` above." to
   the 3-line comment from Step 1.

The `cutover` CTE stays for the Focus branch.

- [ ] **Step 3: Verify no PowerSchool-side reference remains**

```bash
grep -n "focus_start_academic_year\|focus_start_yearid\|is_focus_covered_year" \
  src/dbt/kipptaf/models/students/intermediate/int_students__{ada,attendance_daily,attendance_streak,calendar_day,calendar_rollup,calendar_week,final_grades,gpa}.sql
```

Expected per file: exactly 2 hits, the `cutover`/`sis_cutover` CTE select and
the Focus-side `where ... >= c.focus_start_academic_year` (or `sc.`). No
`- 1990`, no `focus_start_yearid`, no `is_focus_covered_year`.

- [ ] **Step 4: Compile and check Miami rows by year**

```bash
uv run dbt compile --target prod KIPPTAF --select int_students__ada int_students__attendance_daily int_students__attendance_streak int_students__calendar_day int_students__calendar_rollup int_students__calendar_week int_students__final_grades int_students__gpa
```

For each, run the compiled SQL through the BigQuery MCP as
`select academic_year, count(*) as n from (<compiled sql>) where _dbt_source_project = 'kippmiami' group by 1 order by 1`
and the same against `teamster-332318.kipptaf_students.<model>`. Expected:
identical rows for every year, and for `calendar_day` no null `academic_year`
row in the new result (prod today has 1,210; after Task 2 and this task the
remaining count is the 118 historical no-term days; if it is not 118, look at
the dates before deciding).

The compiled SQL of these 8 refs the prod `int_powerschool__*` wrappers, which
still carry Task 5's macro until merge. That does not change counts: the macro
is a no-op on prefixed rows.

- [ ] **Step 5: Lint and commit**

Commit message:
`refactor(kipptaf): drop the PowerSchool-side Miami cutover predicate from 8 students models`

---

### Task 7: Repoint the 3 Miami readers

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippmiami_payout_roster.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__state_test_scores.sql`

**Interfaces:**

- Consumes: `int_students__students` (`student_number`, `enroll_status`,
  `_dbt_source_project`), `int_students__student_enrollments` (`student_number`,
  `fleid`, `rn_year`, `_dbt_source_project`).
- Produces: 3 models with no join on the bare `powerschool_id`.

- [ ] **Step 1: Fix the KIPP Forward roster joins**

In `rpt_gsheets__kippfwd_miami_roster.sql`:

1. The `ps_xwalk` CTE comment says `powerschool_id` "is the PowerSchool
   student_number and NOT studentid, so bridge it to studentid here". Replace
   the comment with:

   ```sql
    /* The archive was rebuilt with student_number 8400-prefixed to the Focus
       id (#5012), so the roster's Focus student_number joins it directly.
       studentid still comes from here because gpa_cumulative keys on it.
       schoolid comes along to keep the gpa_cumulative join single-rowed --
       323 Miami students have more than one row there. */
   ```

2. Change `left join ps_xwalk as px on s.powerschool_id = px.ps_student_number`
   to `left join ps_xwalk as px on e.student_number = px.ps_student_number`.
3. Change the `int_extracts__student_enrollments` join predicate
   `on s.powerschool_id = psy.student_number` to
   `on e.student_number = psy.student_number`.
4. In the `students` CTE, delete `powerschool_id,`. Change the output column
   `cast(s.powerschool_id as int64) as ps_id,` to
   `if(px.ps_student_number is not null, e.student_number - 8400000000, null) as ps_id,`.
   The sheet's `ps_id` keeps meaning "the old PowerSchool number": the archive
   row proves the student had one, and Focus-native students stay null as they
   are today.

- [ ] **Step 2: Repoint the payout roster's DIBELS join**

In `rpt_gsheets__kippmiami_payout_roster.sql`, the DIBELS branch joins
`{{ ref("stg_powerschool__students") }} as s` with
`regexp_extract(s._dbt_source_relation, r'(kipp\w+)_') = 'kippmiami'`. Replace
that join with:

```sql
        inner join
            {{ ref("int_students__students") }} as s
            on amp.student_number = s.student_number
            and s.enroll_status = 0
            and s._dbt_source_project = 'kippmiami'
```

The archive's `enroll_status` is frozen at the retirement date (1,114 rows still
read 0); `int_students__students` reads Focus for Miami. The measure is pinned
to `academic_year = 2024`, so the row count should match the baseline from Task
1 exactly if the Focus and archive active sets agree; a small delta is expected
and acceptable, and Task 9 records it.

- [ ] **Step 3: Repoint the DeansList FAST branch**

In `rpt_deanslist__state_test_scores.sql`, the second `select` reads
`stg_powerschool__students as co` joined to
`stg_powerschool__u_studentsuserfields as suf` for `fleid`. Replace its `from`
and both joins with:

```sql
from
    (
        select distinct student_number, fleid,
        from {{ ref("int_students__student_enrollments") }}
        where _dbt_source_project = 'kippmiami' and fleid is not null
    ) as co
inner join {{ ref("stg_fldoe__fast") }} as fl on co.fleid = fl.student_id
```

`co.student_number` in the select list and the window
`partition by co.student_number` stay as written.

- [ ] **Step 4: Compile and compare with the Task 1 baselines**

```bash
uv run dbt compile --target prod KIPPTAF --select rpt_gsheets__kippfwd_miami_roster rpt_gsheets__kippmiami_payout_roster rpt_deanslist__state_test_scores
```

Run the Task 1 aggregate queries against each compiled SQL (wrap the compiled
SQL as a subquery). Expected:

- kippfwd: same row count per year as baseline; `with_ada` and `with_gpa` rise
  from 0 to roughly the number of returning students (hundreds, not 0).
- payout: same or near-same row count per year.
- state_test_scores: FAST `students` per year equal or higher than baseline
  (Focus carries `fleid` for post-cutover students the archive lacks).

- [ ] **Step 5: Lint and commit**

Commit message:
`fix(kipptaf): repoint 3 Miami readers off the bare PowerSchool number and the frozen students table`

---

### Task 8: PII tags on 6 package models

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__final_grades_rollup.yml`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_term_current.yml`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_term_pivot.yml`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpprogress_grades.yml`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__log.yml`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__s_nj_stu_x_unpivot.yml`

**Interfaces:**

- Produces: column-level `config: meta: contains_pii: true` per
  `.claude/rules/ferpa-pii.md` tiers 2 and 3. No tag on `studentid`,
  `studentsdcid`, `dcid`, ids, or names of plans, courses, or schools.

- [ ] **Step 1: Add the tag block to each listed column**

Under each column below, add (indented to match the file's column entries):

```yaml
config:
  meta:
    contains_pii: true
```

Columns to tag:

- `final_grades_rollup`: `enrolled_credit_hours`, `n_failing`, `n_failing_core`,
  `projected_credits_y1_term`
- `gpa_term_pivot`: `gpa_term_cur`, `gpa_term_q1`, `gpa_term_q2`, `gpa_term_q3`,
  `gpa_term_q4`, `gpa_y1_cur`, `gpa_y1_q1`, `gpa_y1_q2`, `gpa_y1_q3`,
  `gpa_y1_q4`
- `gpprogress_grades`: `teacher_name`, `letter_grade`, `credit_status`,
  `official_potential_credits`, `potential_credits`, `earned_credits`, and the
  15 `plan_*_credits`, `discipline_*_credits`, `subject_*_credits` columns
- `log`: `entry`, `log_type`, `entry_date`
- `s_nj_stu_x_unpivot`: `is_iep_eligible`, `is_portfolio_eligible`,
  `met_requirement`, `values_column`

- [ ] **Step 2: Give `gpa_term_current` a columns block**

The file is 4 lines with no columns. Replace it with:

```yaml
models:
  - name: int_powerschool__gpa_term_current
    description: >-
      int_powerschool__gpa_term filtered to the current term per student and
      school. Ephemeral; consumers read it through the district wrapper.
    config:
      materialized: ephemeral
    columns:
      - name: studentid
        data_type: int64
      - name: schoolid
        data_type: int64
      - name: yearid
        data_type: int64
      - name: term_name
        data_type: string
      - name: semester
        data_type: string
      - name: is_current
        data_type: boolean
      - name: gpa_term
        data_type: float64
        config:
          meta:
            contains_pii: true
      - name: gpa_y1
        data_type: float64
        config:
          meta:
            contains_pii: true
      - name: gpa_y1_unweighted
        data_type: float64
        config:
          meta:
            contains_pii: true
      - name: n_failing_y1
        data_type: int64
        config:
          meta:
            contains_pii: true
      - name: gpa_semester
        data_type: float64
        config:
          meta:
            contains_pii: true
```

Check the data types against
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_term.yml`
before writing; copy that file's `data_type` for each of these columns. Add any
of the remaining 14 columns from the SQL only if the ephemeral model has a
contract (it does not today), so this partial list is acceptable.

- [ ] **Step 3: Parse the package through a consuming district and lint**

```bash
uv run dbt parse --target defer --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-kipptaf-pr2/src/dbt/kippnewark --profiles-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-kipptaf-pr2/src/dbt/kippnewark
```

Expected: parse succeeds (a misindented `config` block fails here). Run trunk on
the 6 files.

- [ ] **Step 4: Commit**

Commit message:
`docs(powerschool): tag student-level grade, GPA, log, and IEP columns as PII on the moved models`

---

### Task 9: Gate, verify, open the PR

**Files:**

- Read: `/workspaces/teamster/.claude/scratch/pr2-baseline.md`
- Read: `.github/pull_request_template.md`

- [ ] **Step 1: Column-resolution gate**

```bash
uv run dbt build --empty --select state:modified+ --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod KIPPTAF
```

Expected: every selected node PASS or SKIP; 0 ERROR. A `Name <col> not found`
error means a consumer named a column a wrapper no longer exposes; fix the
consumer, do not restore the column. This run zeroes the selected dev relations;
that is expected.

- [ ] **Step 2: Verdict-model check**

For the 7 verdict models from Task 1, compile with `--target prod` and run the
Task 1 count query against the compiled SQL. Expected: Miami rows 0 for
`int_powerschool__log`, `int_powerschool__state_assessments_transfer_scores`,
`rpt_powerschool__autocomm_teachers` (verify Miami staff are not emitted as new
users: count rows where `_dbt_source_project = 'kippmiami'` is 0), and unchanged
for `rpt_deanslist__designations`, `rpt_deanslist__hs_transcript_programs`,
`rpt_powerschool__autocomm_students`,
`int_extracts__student_enrollments_subjects` (their Miami branch reads Focus).

- [ ] **Step 3: Append the after-side to the scratch file**

Add the after counts next to each before table. Any delta outside the
expectations in Tasks 4 through 7 stops the PR until explained.

- [ ] **Step 4: Lint everything changed**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-kipptaf-pr2
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git diff --name-only origin/main) </dev/null
```

Expected: `No issues`. Run `trunk fmt` on flagged files and re-check.

- [ ] **Step 5: Push and open the PR**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-kipptaf-pr2 push
```

Open with `mcp__github__create_pull_request`, base `main`, body from
`.github/pull_request_template.md`. Summary leads with the two prod regressions
fixed (Task 7 kippfwd join, Task 2 plus Task 6 calendar_day), then the refactor.
`Closes #5197`, `Refs #5012`. Reviewer Notes: the `gpa_term_current` wrapper
decision (ephemeral in the package, so the kipptaf model filters the `gpa_term`
wrapper instead), the 4 stale source entries, and the PII tag scope. For Claude
fold-out: the before/after tables from the scratch file with counts only.

- [ ] **Step 6: Watch CI and review**

Arm a Monitor on `gh pr checks <n> --json name,bucket,state`. dbt Cloud CI
builds `state:modified+` for kipptaf against prod-equivalent sources; it is the
full-graph check this plan's compile-and-query cannot give. When claude-review
posts, invoke `superpowers:receiving-code-review`, then post per-finding
verdicts as a PR comment.

---

## Self-review notes

Spec coverage: `sources-kippmiami.yml` (Task 3), 9 unions (Task 3), 32 unchanged
unions (no task, by design), 7 wrappers plus region source entries (Task 4), 3
macro calls (Task 5), 8 predicates (Task 6), 3 repoints (Task 7), PII tags (Task
8), verification (Tasks 1, 9). The spec's "Verdicts" table is Task 9 Step 2. The
`powerschool_renumbered` CTE has no task because #5188 removed it.

Two spec items this plan changes, both recorded in Task 4: `gpa_term_current` is
ephemeral in the package, so its "wrapper" is a filter over the `gpa_term`
wrapper, and the Miami region entry count is 2, not 3.
