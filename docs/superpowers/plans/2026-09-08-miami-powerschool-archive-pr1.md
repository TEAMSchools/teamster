# Miami PowerSchool Archive, PR 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the 8 PowerSchool-only kipptaf models into the shared
`powerschool` package, and re-include that package in `kippmiami` with 15
post-hooks so one Dagster build rebuilds Miami's frozen archive with the 8400
prefix and the AY2025 bound baked in.

**Architecture:** The package gains 8 intermediate models copied from kipptaf
minus their `_dbt_source_*` columns (constant inside one region). `kippmiami`
adds `../powerschool` back to `packages.yml` with the ODBC staging variant
enabled, `+materialized: table`, and root-project post-hooks on 15 staging
models. kipptaf is not touched in this PR; its copies of the 8 models keep
building until PR 2 replaces them with union wrappers.

**Tech Stack:** dbt (BigQuery), `uv run dbt`, Dagster dbt assets, trunk.

Spec:
`docs/superpowers/specs/2026-09-08-miami-powerschool-retirement-design.md`. Read
the "Package changes (PR 1)" and "kippmiami project changes (PR 1)" sections
before starting.

## Global Constraints

- Never run bare `dbt`; always `uv run dbt --project-dir <abs path>`.
- Worktree:
  `/workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec`.
  Every path below is relative to it. Every git call is `git -C <worktree>`. dbt
  `--state` paths must be absolute
  (`/workspaces/teamster/src/dbt/<project>/target/prod`).
- Do not edit anything under `src/dbt/kipptaf/` in this PR.
- The 15 hooked staging models: `students` (update) and
  `assignmentcategoryassoc`, `assignmentsection`, `attendance`,
  `attendance_code`, `cc`, `fte`, `gen`, `gradecalculationtype`,
  `gradeformulaset`, `gradeschoolconfig`, `prefs`, `storedgrades`, `termbins`,
  `terms` (delete `yearid > 35`).
- Student-number offset: `8400000000`. AY2025 is `yearid = 35`.
- Lint before pushing:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree. Suppress only with
  `trunk-ignore(linter/rule): reason`.
- No PII in commits, PR body, or comments. Row counts are fine.

---

### Task 1: Move the 8 models into the package

**Files:**

- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__final_grades_rollup.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_term_current.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_term_pivot.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpnode.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpprogress_grades.sql`
- Create: `src/dbt/powerschool/models/sis/intermediate/int_powerschool__log.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__s_nj_stu_x_unpivot.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__state_assessments_transfer_scores.sql`
- Create: the matching 8 files under
  `src/dbt/powerschool/models/sis/intermediate/properties/`
- Read only: the kipptaf originals under
  `src/dbt/kipptaf/models/powerschool/intermediate/` and
  `.../intermediate/properties/`

**Interfaces:**

- Consumes: package models `base_powerschool__final_grades`,
  `int_powerschool__gpa_term`, `stg_powerschool__gpnode`,
  `stg_powerschool__gpprogresssubject`,
  `stg_powerschool__gpprogresssubjectearned`,
  `stg_powerschool__gpprogresssubjectenrolled`, `stg_powerschool__storedgrades`,
  `stg_powerschool__gen`, `stg_powerschool__log`, `stg_powerschool__s_nj_stu_x`,
  `stg_powerschool__test`, `stg_powerschool__testscore`,
  `stg_powerschool__studenttest`, `stg_powerschool__studenttestscore`.
- Produces: 8 package models with the kipptaf column set minus
  `_dbt_source_relation` and `_dbt_source_project`. PR 2's kipptaf wrappers
  union these and add both columns back.

- [ ] **Step 1: Copy each SQL file and remove the `_dbt_source_*` references**

For each of the 8 models, `cp` the kipptaf file to the package path, then edit
it. Three edit rules, applied by hand to every file:

1. Delete every output column line that is `_dbt_source_relation,` or
   `_dbt_source_project,` (with or without an alias prefix such as `p.` or
   `g.`), including in `group by` lists and in every `select` of a `union all`.
1. Delete every join predicate line of the form
   `and <a>._dbt_source_project = <b>._dbt_source_project`. If it was the only
   predicate after `on`, keep the `on` predicate that precedes it.
1. Nothing else changes. Keep every `ref()`, `var()`, comment, and `where`.

Worked example, `int_powerschool__final_grades_rollup.sql` after the edit:

```sql
select
    studentid,
    academic_year,
    schoolid,
    storecode,

    sum(potential_credit_hours) as enrolled_credit_hours,

    sum(if(y1_letter_grade_adjusted in ('F', 'F*'), 1, 0)) as n_failing,
    sum(
        if(
            y1_letter_grade_adjusted in ('F', 'F*')
            and credittype in ('ENG', 'MATH', 'SCI', 'SOC'),
            1,
            0
        )
    ) as n_failing_core,
    sum(
        {# TODO: exclude credits if current year Y1 is stored #}
        if(y1_letter_grade_adjusted not in ('F', 'F*'), potential_credit_hours, null)
    ) as projected_credits_y1_term,
from {{ ref("base_powerschool__final_grades") }}
group by studentid, academic_year, schoolid, storecode
```

Worked example, `int_powerschool__log.sql` after the edit:

```sql
select
    log.studentid,
    log.dcid,
    log.logtypeid,
    log.entry_date,
    log.entry,
    log.academic_year,

    gen.name as log_type,
from {{ ref("stg_powerschool__log") }} as `log`
inner join
    {{ ref("stg_powerschool__gen") }} as gen
    on log.logtypeid = gen.id
    and gen.cat = 'logtype'
```

For `int_powerschool__gpnode.sql` the 3 self-joins each lose their
`_dbt_source_project` predicate and keep `on p.id = o.parentid`,
`on o.id = d.parentid`, `on d.id = s.parentid`. For
`int_powerschool__gpprogress_grades.sql` there are 15 `_dbt_source_*`
occurrences: 4 output columns (2 in each `union all` branch, plus 2 in the final
select), and 9 join predicates. For `int_powerschool__gpa_term_pivot.sql` the
`pivot` output list drops both columns and each `union all` branch drops both.

After editing, this must print 0:

```bash
grep -c "_dbt_source" src/dbt/powerschool/models/sis/intermediate/int_powerschool__{final_grades_rollup,gpa_term_current,gpa_term_pivot,gpnode,gpprogress_grades,log,s_nj_stu_x_unpivot,state_assessments_transfer_scores}.sql | grep -v ":0$" | wc -l
```

- [ ] **Step 2: Copy each properties file and remove the `_dbt_source_*`
      entries**

`cp` each kipptaf `properties/<model>.yml` to the package properties dir.
`int_powerschool__state_assessments_transfer_scores` has no kipptaf properties
file; create one that lists its 8 output columns with `data_type` (`test_name`
string, `studentid` int64, `assessment_grade_level` int64, `testscalescore`
float64, `testperformancelevel` string, `testcode` string, `discipline` string,
`subject` string). Confirm types against the kipptaf prod table:

```sql
select column_name, data_type
from `teamster-332318.kipptaf_powerschool.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'int_powerschool__state_assessments_transfer_scores'
order by ordinal_position
```

In every copied file:

1. Delete the `- name: _dbt_source_relation` and `- name: _dbt_source_project`
   column blocks.
1. In any `dbt_utils.unique_combination_of_columns` test, delete the
   `- _dbt_source_relation` and `- _dbt_source_project` list items. Affected:
   `final_grades_rollup`, `gpa_term_pivot`, `gpnode`, `gpprogress_grades`.
1. Delete any `config.meta.source_model` that points at a kipptaf-only model.
   Package `source_model` values must name package models.

- [ ] **Step 3: Parse the package through a consuming district**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec/src/dbt/kippnewark
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec/src/dbt/kippnewark --target dev
```

Expected: parse succeeds. A failure naming a `ref()` means Step 1 left a kipptaf
ref in; a failure naming a column in a test means Step 2 missed a
`_dbt_source_*` list item.

- [ ] **Step 4: Build the 8 models for Newark in dev and compare to the kipptaf
      copies**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec/src/dbt/kippnewark --target dev --favor-state --defer --state /workspaces/teamster/src/dbt/kippnewark/target/prod --select int_powerschool__final_grades_rollup int_powerschool__gpa_term_current int_powerschool__gpa_term_pivot int_powerschool__gpnode int_powerschool__gpprogress_grades int_powerschool__log int_powerschool__s_nj_stu_x_unpivot int_powerschool__state_assessments_transfer_scores
```

Expected: 8 models and their tests pass. Then for each model, via the BigQuery
MCP (`<user>` is the GitHub username, `cbini`):

```sql
select 'dev' as side, count(*) as n
from `teamster-332318.zz_<user>_kippnewark_powerschool.<model>`
union all
select 'prod', count(*)
from `teamster-332318.kipptaf_powerschool.<model>`
where _dbt_source_project = 'kippnewark'
```

Expected: the 2 counts match for every model. For the 4 models with a uniqueness
test, also compare `count(distinct format('%T|%T|...', <key cols>))` on both
sides. A mismatch on `gpa_term_current` or `gpprogress_grades` can be live
drift, because both filter on the current term; re-run both sides within the
same minute before treating it as a bug.

- [ ] **Step 5: Repeat Step 4 for Camden and Paterson**

Same command with `--project-dir .../src/dbt/kippcamden` and
`--state /workspaces/teamster/src/dbt/kippcamden/target/prod`, then Paterson.
Paterson disables `int_powerschool__section_grade_config`; none of the 8 read
it. Expected: same parity.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/powerschool/models/sis/intermediate/*.sql src/dbt/powerschool/models/sis/intermediate/properties/*.yml </dev/null
git -C . add src/dbt/powerschool/models/sis/intermediate/
git -C . commit -m "refactor(dbt): move 8 PowerSchool-only intermediates from kipptaf into the powerschool package

Refs #5012"
```

Use `git add <path>` here because the files are new; `git add -u` would not
stage them.

---

### Task 2: Re-include the package in kippmiami with the archive hooks

**Files:**

- Modify: `src/dbt/kippmiami/packages.yml`
- Modify: `src/dbt/kippmiami/dbt_project.yml` (the `models:` and a new
  `sources:` block)

**Interfaces:**

- Consumes: the `powerschool` package with the ODBC staging variant, the 58
  frozen externals at
  `gs://teamster-kippmiami/dagster/kippmiami/powerschool/<table>/*`.
- Produces: about 120 `kippmiami_powerschool.*` tables, renumbered and bounded,
  once materialized in prod.

- [ ] **Step 1: Add the package**

In `src/dbt/kippmiami/packages.yml`, add under `packages:`:

```yaml
- local: ../powerschool
```

- [ ] **Step 2: Add the models and sources config**

In `src/dbt/kippmiami/dbt_project.yml`, add a `powerschool:` block under
`models:` (sibling of `focus:`) and a top-level `sources:` block:

```yaml
  powerschool:
    +materialized: table
    sis:
      staging:
        dlt:
          +enabled: false
        odbc:
          +enabled: true
          # Miami's PowerSchool is retired. These hooks bake the network's
          # Miami-only fixes into the frozen archive so kipptaf can stop
          # applying them: the 8400 Focus student-number prefix, and an
          # AY2025 (yearid 35) bound that drops the AY2026 scaffold rows.
          # See docs/superpowers/specs/2026-09-08-miami-powerschool-retirement-design.md
          stg_powerschool__students:
            +post-hook: >-
              update {{ this }}
              set student_number = student_number + 8400000000
              where true
          stg_powerschool__assignmentcategoryassoc:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__assignmentsection:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__attendance:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__attendance_code:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__cc:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__fte:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__gen:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__gradecalculationtype:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__gradeformulaset:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__gradeschoolconfig:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__prefs:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__storedgrades:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__termbins:
            +post-hook: delete from {{ this }} where yearid > 35
          stg_powerschool__terms:
            +post-hook: delete from {{ this }} where yearid > 35

sources:
  powerschool:
    sis:
      staging:
        odbc:
          +enabled: true
```

The `where true` on the `update` is required: BigQuery rejects an `update`
without a `where`.

- [ ] **Step 3: Install and parse**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec/src/dbt/kippmiami
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec/src/dbt/kippmiami --target dev
uv run dbt ls --project-dir /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec/src/dbt/kippmiami --target dev --resource-type model --output path | grep -c 'sis/staging/odbc/'
```

Expected: parse succeeds; the count is 82 (every ODBC staging model enabled).
`grep -c 'sis/staging/dlt/'` on the same listing must print 0.

If parse fails on `int_powerschool__contacts` or
`int_powerschool__person_contacts` referencing a disabled staging model, disable
both in the `sis: intermediate:` block the way `kippnewark/dbt_project.yml`
does:

```yaml
intermediate:
  int_powerschool__contacts:
    +enabled: false
  int_powerschool__person_contacts:
    +enabled: false
```

- [ ] **Step 4: Stage the externals into your dev schema and build the whole
      package**

```bash
uv run dbt run-operation stage_external_sources --args "select: powerschool" --vars '{ext_full_refresh: true}' --target dev --project-dir /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec/src/dbt/kippmiami
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec/src/dbt/kippmiami --target dev --select package:powerschool
```

This lands in `zz_<user>_kippmiami_powerschool`, a personal schema, so nothing
in prod changes. Expected: every model builds. Data tests with `severity: warn`
may warn on the frozen data; record any warning in the PR body's "For Claude"
fold-out, do not fix it here. An error on a staging model whose `select` names a
column the frozen file lacks means the package changed since 2026-07-01; disable
that model in kippmiami's `odbc:` block only if nothing in the archive set
(spec, "Archive relations") depends on it, otherwise stop and report.

- [ ] **Step 5: Verify the hooks against the prod frozen copies**

Prefix check, expected 0 bare ids on all 4 (prod today: 3,946 and 7,930 bare on
the first 2):

```sql
select 'students' as t, countif(student_number < 8400000000) as bare, count(*) as n
from `teamster-332318.zz_<user>_kippmiami_powerschool.stg_powerschool__students`
union all select 'ada', countif(student_number < 8400000000), count(*)
from `teamster-332318.zz_<user>_kippmiami_powerschool.int_powerschool__ada`
union all select 'streak', countif(student_number < 8400000000), count(*)
from `teamster-332318.zz_<user>_kippmiami_powerschool.int_powerschool__attendance_streak`
union all select 'ctod', countif(student_number < 8400000000), count(*)
from `teamster-332318.zz_<user>_kippmiami_powerschool.int_powerschool__ps_adaadm_daily_ctod`
```

Bound check, expected 0 for every table in the second column (prod today:
`stg_powerschool__terms` has 21):

```sql
select 'terms' as t, countif(yearid > 35) as over, count(*) as n
from `teamster-332318.zz_<user>_kippmiami_powerschool.stg_powerschool__terms`
union all select 'cc', countif(yearid > 35), count(*)
from `teamster-332318.zz_<user>_kippmiami_powerschool.stg_powerschool__cc`
union all select 'storedgrades', countif(yearid > 35), count(*)
from `teamster-332318.zz_<user>_kippmiami_powerschool.stg_powerschool__storedgrades`
union all select 'attendance', countif(yearid > 35), count(*)
from `teamster-332318.zz_<user>_kippmiami_powerschool.stg_powerschool__attendance`
```

Row parity for the 32 archive relations named in the spec, one query per table:

```sql
select 'dev' as side, count(*) as n
from `teamster-332318.zz_<user>_kippmiami_powerschool.<table>`
union all
select 'prod', count(*)
from `teamster-332318.kippmiami_powerschool.<table>`
where yearid <= 35
```

Drop the `where` for tables without `yearid` (`students`, `schools`, `courses`,
`roledef`, `sectionteacher`, `studentcorefields`, `u_studentsuserfields`,
`gpa_cumulative`); use `academic_year <= 2025` where the table has that column
instead. Expected: equal counts. Record every pair in
`.claude/scratch/pr1-archive-parity.md` (gitignored) and quote the totals in the
PR body.

- [ ] **Step 6: Confirm the Dagster code location still loads**

Write `tests/dagster/test_zz_kippmiami_defs.py`:

```python
import subprocess


def test_kippmiami_definitions_validate():
    subprocess.check_output(
        [
            "uv",
            "run",
            "dagster",
            "definitions",
            "validate",
            "-m",
            "teamster.code_locations.kippmiami.definitions",
        ],
        cwd="/workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec",
    )
```

Run `uv run pytest tests/dagster/test_zz_kippmiami_defs.py -s` from the
worktree. Expected: pass. The package's `sources-external.yml` declares asset
keys `[kippmiami, powerschool, <table>]` that no kippmiami asset produces;
dagster-dbt treats them as external upstreams, which is what we want (no events,
no automatic rebuild). If validation fails on those keys, stop and report; do
not add producer assets. Delete the test file after it passes.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kippmiami/packages.yml src/dbt/kippmiami/dbt_project.yml </dev/null
git -C . add -u
git -C . commit -m "chore(kippmiami): re-include the powerschool package with archive hooks for a one-time rebuild

Refs #5012"
```

---

### Task 3: Document the archive recipe

**Files:**

- Modify: `src/dbt/kippmiami/CLAUDE.md` (the PowerSchool paragraph, currently
  lines 15 to 18)
- Modify: `src/teamster/code_locations/kippmiami/CLAUDE.md` (lines 112 to 113)
- Modify: `src/dbt/powerschool/CLAUDE.md` (the `odbc/` line, currently line 16)

- [ ] **Step 1: kippmiami dbt CLAUDE.md**

Replace the paragraph that begins "PowerSchool (pre-Focus SIS) is retired" with:

```markdown
PowerSchool (pre-Focus SIS) is retired. `kippmiami_powerschool` is an archive
rebuilt once from the frozen `src_powerschool__*` externals (final ODBC pull
2026-07-01) by re-including the `powerschool` package with the ODBC staging
variant and 15 post-hooks in `dbt_project.yml`: `stg_powerschool__students` gets
the 8400 Focus prefix on `student_number`, and the 14 staging models with
`yearid` drop rows past AY2025 (`yearid > 35`). The package is removed again
after the prod build (#5012); the hook YAML in that PR is the rebuild recipe.
kipptaf reads the dataset as a BQ-native source. Do not drop the dataset or the
GCS files.
```

- [ ] **Step 2: kippmiami code-location CLAUDE.md**

Replace the 2 lines "PowerSchool (pre-Focus SIS) is retired — frozen archive in
BigQuery dataset `kippmiami_powerschool`; do not drop." with:

```markdown
PowerSchool (pre-Focus SIS) is retired. `kippmiami_powerschool` is a frozen
archive rebuilt once through the dbt `powerschool` package (#5012); do not drop
the dataset or the GCS files under
`gs://teamster-kippmiami/dagster/kippmiami/powerschool/`.
```

- [ ] **Step 3: powerschool package CLAUDE.md**

Change the `odbc/` description from "ARCHIVED - disabled by default; no district
builds it" to "ARCHIVED - disabled by default; kippmiami enables it for one-off
archive rebuilds (#5012)".

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kippmiami/CLAUDE.md src/teamster/code_locations/kippmiami/CLAUDE.md src/dbt/powerschool/CLAUDE.md </dev/null
git -C . add -u
git -C . commit -m "docs(claude): record the Miami PowerSchool archive rebuild recipe

Refs #5012"
```

---

### Task 4: Push and open the PR

**Files:**

- Create: `.claude/scratch/pr1-body.md` (gitignored draft)

- [ ] **Step 1: Push**

```bash
git -C /workspaces/teamster/.worktrees/cbini/chore/claude-miami-powerschool-retirement-spec push
```

The branch already tracks `origin`.

- [ ] **Step 2: Write the PR body from the template**

Copy `.github/pull_request_template.md` to `.claude/scratch/pr1-body.md` and
fill it in. Keep every template line. Summary:

> When merged, this pull request will move 8 PowerSchool-only intermediate
> models from kipptaf into the shared `powerschool` package, and re-include that
> package in `kippmiami` with 15 post-hooks so one Dagster build rebuilds
> Miami's frozen PowerSchool archive with the 8400 student-number prefix and the
> AY2025 bound applied. kipptaf is unchanged in this PR; PR 2 (#5012) deletes
> its Miami-only steps and swaps the 8 models for union wrappers.

Reviewer Notes, one line each: the post-hooks are `update`/`delete` on the 15
kippmiami tables being rebuilt in the same run; the 8 moved models dropped their
`_dbt_source_*` columns, which the PR 2 wrappers restore; dbt Cloud CI builds
kipptaf only, so it proves nothing here, and the dev-build parity numbers are in
the "For Claude" fold-out.

"For Claude": paste the parity totals from
`.claude/scratch/pr1-archive-parity.md` (counts only), the
Newark/Camden/Paterson parity results from Task 1, and any `severity: warn` test
output from Task 2 Step 4. Check the Dagster and dbt self-review boxes that
apply; leave `stage_external_sources --target staging` unchecked and say why:
the kippmiami externals are prod-only and CI does not build kippmiami.

End the body with `Refs #5012`.

Do not write the bare token `env` anywhere in the body; write "environment".

- [ ] **Step 3: Open the PR**

Use `mcp__github__create_pull_request` with `owner: TEAMSchools`,
`repo: teamster`, `head: cbini/chore/claude-miami-powerschool-retirement-spec`,
`base: main`, title
`refactor(dbt): move PowerSchool-only intermediates into the package and rebuild the Miami archive once`,
and the body from Step 2. Confirm the returned title and body match.

- [ ] **Step 4: Watch CI and review**

Invoke `pr-ci-review`. Expected checks: Trunk passes; dbt Cloud CI passes with
no kipptaf models selected (nothing under `src/dbt/kipptaf/` changed); Dagster
Cloud branch deployment for kippmiami builds. When `claude-review` posts, invoke
`superpowers:receiving-code-review` before acting on it.

---

## After merge (user-run, not part of this plan's commits)

1. NJ regions: the 8 new package models materialize on each region's next
   upstream update. Confirm in Dagster that
   `kippnewark/powerschool/int_powerschool__final_grades_rollup` (and the other
   7, for each region) has a materialization.
1. Miami: Dagster UI, code location `kippmiami`, asset group `powerschool`,
   materialize all. About 120 models. Branch deployments read
   `gs://teamster-test`, so this must run on prod.
1. Re-run the Task 2 Step 5 queries against `kippmiami_powerschool` instead of
   the dev schema. Expected: same results as dev.
1. Then PR 1b (remove the include) and PR 2 (kipptaf), each with its own plan.

## Self-review notes

- Spec coverage: "Package changes (PR 1)" is Task 1; "kippmiami project changes
  (PR 1)" is Task 2; the CLAUDE.md line in the spec is Task 3; "Delivery" step 1
  is Task 4 and step 2 is "After merge". The spec's `fldoe` source block stays
  untouched, as written.
- Type consistency: the 8 model names are identical across Tasks 1, 4, and the
  spec. The hook list matches the spec's 15 tables.
- The spec's PR 1 verification (prefix, bound, parity) runs in dev in Task 2
  Step 5 and again in prod after merge.
