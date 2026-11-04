# FRESH Scaffold Package Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure PR #4488's FRESH-dashboard changes so shared
Finalsite/Focus transformation logic lives in the source-system packages, the
enrollment scaffold is a plain blend-only model (no var, no Jinja mode switch),
and the grade-level sentinel scheme is PK = `-1` / whole-school total = `-9`.

**Architecture:** Three moves — (1) promote source-cleaning logic from kipptaf's
`stg_finalsite__status_report` union wrapper into the `finalsite` package
staging model; (2) rewrite the orphaned `focus` package model
`int_focus__student_enrollment` to carry the full Focus-native enrollment
derivation, leaving kipptaf's `int_focus__student_enrollments` as a thin
cross-source wrapper; (3) collapse `int_finalsite__enrollment_scaffold` to its
blend implementation and re-key sentinels. Spec:
`docs/superpowers/specs/2026-07-28-fresh-scaffold-package-refactor-design.md`.

**Tech Stack:** dbt (BigQuery), `uv run dbt`, trunk (sqlfluff/sqlfmt,
markdownlint), git worktree.

## Global Constraints

- **Worktree:** ALL file edits target
  `/workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages`
  (branch `cbini/refactor/claude-fresh-scaffold-packages`, stacked on
  `grangel/feat/claude-fresh-scaffold-swap`). Use `git -C <worktree>` for every
  git command. Editing `/workspaces/teamster/<path>` instead silently dirties
  `main`.
- **dbt:** always `uv run dbt ... --project-dir <worktree>/src/dbt/<project>`
  from the main repo cwd. Never bare `dbt`. Run
  `uv run dbt deps --project-dir <worktree>/src/dbt/<project>` once per project
  before its first build in the worktree.
- **trunk:** binary is `/workspaces/teamster/.trunk/tools/trunk`; run with cwd
  INSIDE the worktree, `--force --no-fix </dev/null`, naming changed files.
  Pre-commit hook only formats; sqlfluff/yamllint fire at push/CI.
- **SQL conventions** (`src/dbt/CLAUDE.md`, sqlfluff-enforced): no `ORDER BY` /
  `QUALIFY` / table subqueries (pre-existing `not in (select ...)` in the
  status-report wrapper is grandfathered — do not add new ones); max 1 level of
  function nesting; ST06 column ordering (plain refs by table, then constants,
  simple functions, nested functions, logicals, case, window); trailing commas;
  staging tests need explicit `severity: error`; generic tests use `arguments:`
  nesting.
- **Sentinels:** PK = `-1` (decoded from `PK`/`Prekindergarten` grade strings);
  whole-school total = `-9` (recoded from the sheets' `-1` at the Google-Sheets
  staging models). `-1` and `-9` must never both mean school-total anywhere
  after this refactor.
- **Vars:** `finalsite_recruitment_year` stays. `finalsite_scaffold_source` is
  deleted everywhere.
- **Commit style:** conventional commits. One commit per task.
- **Subagents:** IDE Pyright/sqlfluff diagnostics on worktree files are
  false-positive-prone; trust `uv run dbt` + trunk run inside the worktree.

---

### Task 1: Finalsite package promotion + kipptaf wrapper slim-down

**Files:**

- Modify:
  `src/dbt/finalsite/models/sftp/staging/stg_finalsite__status_report.sql`
- Modify:
  `src/dbt/finalsite/models/sftp/staging/properties/stg_finalsite__status_report.yml`
- Modify:
  `src/dbt/kipptaf/models/finalsite/staging/stg_finalsite__status_report.sql`
- Modify:
  `src/dbt/kipptaf/models/finalsite/staging/properties/stg_finalsite__status_report.yml`

**Interfaces:**

- Consumes: raw `source("finalsite", "status_report")` columns
  (`application_grade`, `enrollment_type`, `first_name`, `active_school_year`).
- Produces: package `stg_finalsite__status_report` gains `grade_level` (int64)
  and `active_school_year_display` (string); `first_name` and `enrollment_type`
  are transformed in place. The kipptaf wrapper passes all of these through via
  `union_relations` and keeps ONLY `region`, `_dbt_source_project`, and the
  `exclude_ids` filter. Downstream (`int_finalsite__status_report_unpivot`, Task
  5's models) sees identical column names/types to PR #4488's output — except
  the PK decode value, which stays `-1` (unchanged from #4488).

- [ ] **Step 1: Move the four transformations into the package model**

In `src/dbt/finalsite/models/sftp/staging/stg_finalsite__status_report.sql`,
inside the `status_report` CTE: delete the plain `first_name,` and
`enrollment_type,` lines from the column enumeration, and add to the
function/case section of that CTE (after the existing `cast(...)` columns,
before `active_school_year_int`):

```sql
initcap(first_name) as first_name,

initcap(coalesce(enrollment_type, 'New')) as enrollment_type,

regexp_replace(active_school_year, r'-\d{2}', '-') as active_school_year_display,

case
    when application_grade in ('PK', 'Prekindergarten')
    then -1
    when application_grade in ('K', 'Kindergarten')
    then 0
    else cast(regexp_extract(application_grade, r'\d+') as int)
end as grade_level,
```

Keep the raw `active_school_year` column (already in the contract). Respect
ST06: the `case` goes after the simple functions. Note the PR's
`if(enrollment_type is null, 'New', enrollment_type)` becomes
`coalesce(enrollment_type, 'New')` — same semantics, one nesting level under
`initcap`.

- [ ] **Step 2: Declare the new columns + tests in the package yml**

In
`src/dbt/finalsite/models/sftp/staging/properties/stg_finalsite__status_report.yml`,
add contract entries (staging is contract-enforced) and move the grade-domain
tests here from kipptaf:

```yaml
- name: grade_level
  data_type: int64
  description: >-
    Numeric grade level derived from application_grade — K/Kindergarten = 0,
    PK/Prekindergarten = -1, else the parsed digit grade. No district currently
    recruits PK through Finalsite, so the PK match is unverified against a real
    raw value; not_null makes any unrecognized grade string (which parses to
    null) fail loudly.
  data_tests:
    - not_null:
        config:
          severity: error
    - accepted_values:
        arguments:
          values: [-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
          quote: false
        config:
          severity: error
- name: active_school_year_display
  data_type: string
  description: >-
    active_school_year with the two-digit end-year suffix collapsed (e.g.
    2026-27 to 2026-), for display concatenation downstream.
```

Sort `grade_level` (has per-column tests) toward the top of the `columns:` list
per repo convention. Update the transformed columns' descriptions (`first_name`
— initcap-normalized; `enrollment_type` — initcap-normalized, null = New).

- [ ] **Step 3: Slim the kipptaf wrapper**

Replace the body of
`src/dbt/kipptaf/models/finalsite/staging/stg_finalsite__status_report.sql`
(keep the `union_relations` CTE with its four `source(...)` entries exactly
as-is) so the final select is:

```sql
select
    *,

    initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

    {{ extract_source_project() }} as _dbt_source_project,

from union_relations
where
    finalsite_enrollment_id not in (
        select x.finalsite_student_id,
        from {{ ref("stg_google_sheets__finalsite__exclude_ids") }} as x
    )
```

i.e. delete the `* except (first_name, enrollment_type)` projection, the
`initcap(first_name)`, the `active_school_year_display` regexp, the
`grade_level` case, and the `enrollment_type` initcap/default — all now
package-side. The `where ... not in` filter is pre-existing; leave it.

- [ ] **Step 4: Update the kipptaf yml**

In
`src/dbt/kipptaf/models/finalsite/staging/properties/stg_finalsite__status_report.yml`:
keep the `grade_level` and `active_school_year_display` contract entries (they
still flow through the union), but (a) delete the `accepted_values` test and its
config from `grade_level` (now enforced at the package), (b) replace the
`grade_level` description with: derived in the finalsite package staging model —
see `stg_finalsite__status_report` there for the decode and sentinel scheme
(`-1` = PK). Delete the "mirroring PowerSchool's Pre-K convention" sentence
wherever it appears.

- [ ] **Step 5: Compile-check both projects**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/kippnewark
uv run dbt parse --target prod --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/kippnewark
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/kipptaf
uv run dbt parse --target prod --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/kipptaf
```

Expected: both parse clean (no contract/ref errors).

- [ ] **Step 6: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/finalsite/models/sftp/staging/stg_finalsite__status_report.sql \
  src/dbt/finalsite/models/sftp/staging/properties/stg_finalsite__status_report.yml \
  src/dbt/kipptaf/models/finalsite/staging/stg_finalsite__status_report.sql \
  src/dbt/kipptaf/models/finalsite/staging/properties/stg_finalsite__status_report.yml </dev/null
```

Fix any ST06/CV03 ordering complaints by moving columns between the
enumeration/function/case sections.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages add \
  src/dbt/finalsite/models/sftp/staging/stg_finalsite__status_report.sql \
  src/dbt/finalsite/models/sftp/staging/properties/stg_finalsite__status_report.yml \
  src/dbt/kipptaf/models/finalsite/staging/stg_finalsite__status_report.sql \
  src/dbt/kipptaf/models/finalsite/staging/properties/stg_finalsite__status_report.yml
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages commit -m "refactor(dbt): promote status_report transforms into finalsite package"
```

---

### Task 2: Focus package — full derivation in `int_focus__student_enrollment`

**Files:**

- Modify: `src/dbt/focus/models/intermediate/int_focus__student_enrollment.sql`
  (full rewrite — zero consumers exist)
- Modify:
  `src/dbt/focus/models/intermediate/properties/int_focus__student_enrollment.yml`

**Interfaces:**

- Consumes: package refs `stg_focus__students`, `stg_focus__student_enrollment`,
  `stg_focus__schools`, `stg_focus__school_gradelevels`,
  `stg_focus__student_enrollment_codes`,
  `stg_focus__custom_field_select_options`, `int_focus__school_year_first_day`
  (all exist in the package; NO `_dbt_source_project` join keys — this is a
  single-district package context, that column is added by kipptaf's union
  wrapper).
- Produces: one row per Focus enrollment stint with columns (exact names Task
  3's wrapper passes through): `student_enrollment_id`, `academic_year`,
  `academic_year_display`, `schoolid`, `school_number`, `school_title`,
  `school_state_school_id`, `state`, `startdate`, `exitdate`, `entrycode`,
  `exitcode`, `grade_level`, `grade_level_short_name`, `student_number`,
  `student_first_name`, `student_last_name`, `student_name`, `student_email`,
  `fteid`, `dob`, `enroll_status`, `school_level`, `first_day_of_school`,
  `is_enrolled_fdos`, `is_enrolled_oct01`, `is_enrolled_oct15`,
  `is_enrolled_mar15`, `is_pre_year_withdrawal`, `rn_year`, `year_in_school`,
  `year_in_network`.

- [ ] **Step 1: Rewrite the model**

Replace `src/dbt/focus/models/intermediate/int_focus__student_enrollment.sql`
with:

```sql
with
    enrollment as (
        select
            s.first_name as student_first_name,
            s.last_name as student_last_name,
            s.florida_education_identifier as fteid,
            s.student_e_mail_address as student_email,

            e.id as student_enrollment_id,
            e.syear as academic_year,
            e.school_id as schoolid,
            e.start_date as startdate,

            sch.title as school_title,
            sch.state_school_id as school_state_school_id,
            sch.school_number,
            sch.state,

            g.short_name as grade_level_short_name,

            ec.short_name as entrycode,

            dc.short_name as exitcode,

            fd.first_day_of_school,

            s.student_id as student_number,

            cast(s.birthdate as date) as dob,

            concat(s.last_name, ', ', s.first_name) as student_name,

            cast(e.syear as string)
            || '-'
            || right(cast(e.syear + 1 as string), 2) as academic_year_display,

            coalesce(e.end_date, date(e.syear + 1, 6, 30)) as exitdate,

            case
                g.short_name
                when 'PK'
                then -1
                when 'KG'
                then 0
                else cast(regexp_extract(g.short_name, r'\d+') as int)
            end as grade_level,

            case
                when dc.grad_type = 'graduated'
                then 3
                when e.drop_code is not null
                then 2
                else 0
            end as enroll_status,

            case
                slo.code when 'E' then 'ES' when 'M' then 'MS' when 'H' then 'HS'
            end as school_level,

        from {{ ref("stg_focus__students") }} as s
        inner join
            {{ ref("stg_focus__student_enrollment") }} as e
            on s.student_id = e.student_id
        left join {{ ref("stg_focus__schools") }} as sch on e.school_id = sch.id
        left join
            {{ ref("stg_focus__custom_field_select_options") }} as slo
            on sch.school_level = slo.id
            and slo.source_class = 'CustomField'
        left join
            {{ ref("stg_focus__school_gradelevels") }} as g
            on e.grade_id = g.id
            and e.school_id = g.school_id
            and g.short_name != '30'
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as ec
            on e.enrollment_code = ec.id
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as dc
            on e.drop_code = dc.id
        -- TODO: first day is network-wide per syear; if per-school calendar
        -- variance matters (or a second Focus region onboards), key this by
        -- school as well.
        left join
            {{ ref("int_focus__school_year_first_day") }} as fd
            on e.syear = fd.syear
    ),

    with_flags as (
        select
            *,

            if(startdate <= first_day_of_school, true, false) as is_enrolled_fdos,

            if(
                date(academic_year, 10, 1) between startdate and exitdate, true, false
            ) as is_enrolled_oct01,

            if(
                date(academic_year, 10, 15) between startdate and exitdate, true, false
            ) as is_enrolled_oct15,

            if(
                date(academic_year + 1, 3, 15) between startdate and exitdate,
                true,
                false
            ) as is_enrolled_mar15,

            if(exitdate < first_day_of_school, true, false) as is_pre_year_withdrawal,

            row_number() over (
                partition by student_number, academic_year
                order by academic_year desc, exitdate desc
            ) as rn_year,
        from enrollment
    ),

    with_year_counts as (
        select
            *,

            row_number() over (
                partition by student_number, schoolid, rn_year
                order by academic_year asc, exitdate asc
            ) as year_in_school,

            row_number() over (
                partition by student_number, rn_year
                order by academic_year asc, exitdate asc
            ) as year_in_network,
        from with_flags
    )

select
    * except (year_in_school, year_in_network),

    if(rn_year = 1, year_in_school, null) as year_in_school,

    if(rn_year = 1, year_in_network, null) as year_in_network,

from with_year_counts
```

Notes: this drops the old model's raw-id passthroughs (`grade_id`,
`enrollment_code`, `drop_code`, `calendar_id`, `grade_level_title`,
`enrollment_code_*`) — zero consumers, YAGNI. `region`, `region_school_level`,
`district`, the Finalsite-ID join, and the locations crosswalk are deliberately
ABSENT — they are cross-source/kipptaf concerns (Task 3).

- [ ] **Step 2: Rewrite the properties yml**

Replace the model block in
`src/dbt/focus/models/intermediate/properties/int_focus__student_enrollment.yml`:
keep `name: int_focus__student_enrollment`; update the description to describe
the full derivation (enrollment stints with student attributes, decoded grade
level — `PK` = -1, `KG` = 0 — resolved entry/exit codes, `enroll_status` [0
enrolled / 2 withdrawn / 3 graduated], June-30 default exitdate for open stints,
network-first-day point-in-time flags, and `rn_year` / `year_in_school` /
`year_in_network` counters mirroring the PowerSchool enrollment-union
conventions; internal-only). Column list: `student_enrollment_id` first with

```yaml
data_tests:
  - unique:
      config:
        severity: error
  - not_null:
      config:
        severity: error
```

then every column from the Produces list above with a one-line description each.
Tag `contains_pii: true` on `student_number`, `student_first_name`,
`student_last_name`, `student_name`, `student_email`, `fteid`, `dob`.

- [ ] **Step 3: Build into dev via kippmiami**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/kippmiami
uv run dbt build --select int_focus__student_enrollment \
  --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: model builds into `zz_cbini_kippmiami_focus` and the `unique` +
`not_null` tests PASS. (This dev relation is also what Task 3's kipptaf dev
build reads via the dev source-schema prefix — do not skip this step.)

- [ ] **Step 4: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/focus/models/intermediate/int_focus__student_enrollment.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__student_enrollment.yml </dev/null
```

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages add \
  src/dbt/focus/models/intermediate/int_focus__student_enrollment.sql \
  src/dbt/focus/models/intermediate/properties/int_focus__student_enrollment.yml
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages commit -m "refactor(dbt): full Focus enrollment derivation in focus package intermediate"
```

---

### Task 3: kipptaf Focus wrapper + passthrough deletion

**Files:**

- Modify:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__student_enrollments.sql`
  (full rewrite as thin wrapper)
- Modify:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_enrollments.yml`
- Modify: `src/dbt/kipptaf/models/focus/sources-kippmiami.yml`
- Delete:
  `src/dbt/kipptaf/models/focus/staging/stg_focus__school_gradelevels.sql`
- Delete:
  `src/dbt/kipptaf/models/focus/staging/stg_focus__student_enrollment_codes.sql`
- Delete:
  `src/dbt/kipptaf/models/focus/staging/stg_focus__custom_field_select_options.sql`
- Delete:
  `src/dbt/kipptaf/models/focus/staging/properties/stg_focus__school_gradelevels.yml`
- Delete:
  `src/dbt/kipptaf/models/focus/staging/properties/stg_focus__student_enrollment_codes.yml`
- Delete:
  `src/dbt/kipptaf/models/focus/staging/properties/stg_focus__custom_field_select_options.yml`

**Interfaces:**

- Consumes: `source("kippmiami_focus", "int_focus__student_enrollment")` (Task
  2's column set), `int_finalsite__contact_id_attributes`
  (`_dbt_source_project`, `finalsite_enrollment_id`,
  `focus_student_id_prefixed`), `stg_google_sheets__people__locations`
  (`focus_school_id`, `powerschool_school_id`, `location_name`, `abbreviation`,
  `reporting_school_id`, `location_region`, `deanslist_school_id`).
- Produces: the SAME output columns PR #4488's version produced (verify against
  the existing yml) — `int_tableau__finalsite_student_scaffold` consumes this
  model and must not need changes. Key additions over Task 2's package columns:
  `_dbt_source_relation`, `_dbt_source_project`, `region`,
  `region_school_level`, `district`, `finalsite_enrollment_id`, `ps_schoolid`,
  `school`, `school_abbreviation`, `reporting_schoolid`, `region_official_name`,
  `deanslist_school_id`.

- [ ] **Step 1: Rewrite the wrapper**

Replace
`src/dbt/kipptaf/models/focus/intermediate/int_focus__student_enrollments.sql`
with:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__student_enrollment"),
                ]
            )
        }}
    ),

    enrollments as (
        select
            *,

            {{ extract_source_project("union_relations") }} as _dbt_source_project,

            {{ extract_region("union_relations") }} as region,
        from union_relations
    ),

    finalsite_ids as (
        select
            _dbt_source_project,
            finalsite_enrollment_id,

            cast(focus_student_id_prefixed as int) as focus_student_id,
        from {{ ref("int_finalsite__contact_id_attributes") }}
    )

select
    e.*,

    loc.powerschool_school_id as ps_schoolid,
    loc.location_name as school,
    loc.abbreviation as school_abbreviation,
    loc.reporting_school_id as reporting_schoolid,
    loc.location_region as region_official_name,
    loc.deanslist_school_id,

    f.finalsite_enrollment_id,

    'KTAF' as district,

    concat(e.region, e.school_level) as region_school_level,

from enrollments as e
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on e.school_number = loc.focus_school_id
left join
    finalsite_ids as f
    on e.student_number = f.focus_student_id
    and e._dbt_source_project = f._dbt_source_project
```

Check the `extract_region` macro signature first
(`git grep -n 'macro extract_region' src/dbt`) — if it derives from
`_dbt_source_relation` (like `extract_source_project`) the call above is right;
if it expects a table alias with different columns, replicate what PR #4488's
version passed (`{{ extract_region("s") }}` over a unioned staging model) and
adapt. `student_enrollment_id` also renames: the PR version aliased
`e.id as student_enrollment_id` — Task 2 already outputs the final name, so no
alias needed here.

- [ ] **Step 2: Update the wrapper yml**

In
`src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_enrollments.yml`:
keep the model name, the `unique` + `not_null` `student_enrollment_id` tests,
and the full column list (output shape is unchanged). Update the model
description: derivation now lives in the focus package
(`int_focus__student_enrollment`); this model unions the district relation and
adds the Finalsite-ID crosswalk, location enrichment, and region/network
constants.

- [ ] **Step 3: Rewire sources and delete passthroughs**

In `src/dbt/kipptaf/models/focus/sources-kippmiami.yml`: delete the three table
blocks `stg_focus__school_gradelevels`, `stg_focus__student_enrollment_codes`,
`stg_focus__custom_field_select_options`; add:

```yaml
- name: int_focus__student_enrollment
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - int_focus__student_enrollment
```

Delete the six passthrough files listed in **Files**. Then confirm nothing else
references them:

```bash
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages grep -n \
  'stg_focus__school_gradelevels\|stg_focus__student_enrollment_codes\|stg_focus__custom_field_select_options' \
  -- src/dbt/kipptaf
```

Expected: no matches (or only the sources file if a deletion was missed).

- [ ] **Step 4: Build the wrapper into dev**

```bash
uv run dbt build --select int_focus__student_enrollments \
  --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: builds (dev source prefix resolves `kippmiami_focus` to
`zz_cbini_kippmiami_focus`, populated by Task 2 Step 3) and the `unique` test on
`student_enrollment_id` PASSES. Then verify output-shape parity — compare column
sets between this dev build and the PR-era model:

```sql
select column_name
from `teamster-332318`.zz_cbini_kipptaf_focus.INFORMATION_SCHEMA.COLUMNS
where table_name = 'int_focus__student_enrollments'
order by column_name
```

against the column list in the (unchanged-shape) properties yml. Any column the
yml lists but the build lacks is a wrapper bug — fix before committing.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__student_enrollments.sql \
  src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_enrollments.yml \
  src/dbt/kipptaf/models/focus/sources-kippmiami.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages add \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__student_enrollments.sql \
  src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_enrollments.yml \
  src/dbt/kipptaf/models/focus/sources-kippmiami.yml \
  src/dbt/kipptaf/models/focus/staging/stg_focus__school_gradelevels.sql \
  src/dbt/kipptaf/models/focus/staging/stg_focus__student_enrollment_codes.sql \
  src/dbt/kipptaf/models/focus/staging/stg_focus__custom_field_select_options.sql \
  src/dbt/kipptaf/models/focus/staging/properties/stg_focus__school_gradelevels.yml \
  src/dbt/kipptaf/models/focus/staging/properties/stg_focus__student_enrollment_codes.yml \
  src/dbt/kipptaf/models/focus/staging/properties/stg_focus__custom_field_select_options.yml
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages commit -m "refactor(dbt): thin kipptaf focus wrapper over package intermediate"
```

---

### Task 4: Scaffold collapse (blend-only, region anti-join, var removal)

**Files:**

- Modify:
  `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__enrollment_scaffold.sql`
- Modify:
  `src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__enrollment_scaffold.yml`
- Modify: `src/dbt/kipptaf/dbt_project.yml`

**Interfaces:**

- Consumes: `stg_powerschool__schools`, `stg_powerschool__students`,
  `stg_google_sheets__finalsite__school_scaffold`,
  `var("finalsite_recruitment_year")`.
- Produces: same contract as before — `schoolid`, `school`, `region`,
  `grade_level`, `academic_year`, `org`, `scaffold_source`, `school_level`.
  Consumers (`int_finalsite__goals_scaffold`,
  `rpt_tableau__fresh_dashboard_progress_to_goals`, the region-mismatch test)
  need no changes from this task.

- [ ] **Step 1: Rewrite the model**

Replace
`src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__enrollment_scaffold.sql`:
delete the `{% set scaffold_source_mode ... %}` line, the entire
`{% if scaffold_source_mode not in ... %}` `raise_compiler_error` block, the
`{% if scaffold_source_mode in ("gsheet", "blend") %}` guard around
`gsheet_scaffold` (keep the CTE unconditionally), and the three-way `{% if %}`
final-select branching — keep ONLY the blend branch (the `union all` +
anti-join). Keep every CTE (`powerschool_region`, `powerschool_schools`,
`current_grade_levels`, `grade_membership`, `powerschool_scaffold`,
`gsheet_scaffold`) and their comments, with two edits:

1. In the anti-join, add the region key:

```sql
    left join
        powerschool_scaffold as p
        on g.region = p.region
        and g.schoolid = p.schoolid
        and g.grade_level = p.grade_level
    where p.schoolid is null
```

1. Update the two comments that reference `finalsite_scaffold_source` /
   mode-switching (the Miami carve-out comment: "regardless of
   `finalsite_scaffold_source`" becomes "regardless of scaffold source"; the
   `current_grade_levels` comment's `grade_level = -1` sentinel reference
   becomes `-9` — Task 5 lands the recode, but this file's comments say `-9` now
   so the two commits read consistently; note the cross-reference).

- [ ] **Step 2: Remove the var**

In `src/dbt/kipptaf/dbt_project.yml`, delete the single line:

```yaml
finalsite_scaffold_source: blend # 'gsheet' | 'powerschool' (debug only, see model description) | 'blend'
```

Keep `finalsite_recruitment_year: 2026` and its comment block untouched. Then
verify zero remaining references:

```bash
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages grep -rn 'finalsite_scaffold_source' -- src/dbt
```

Expected: no matches. (Docs/skill references are Task 6's job — check with
`--include` off only within `src/dbt` here.)

- [ ] **Step 3: Rewrite the model yml description**

In `properties/int_finalsite__enrollment_scaffold.yml`: replace the mode-switch
description (lines describing `finalsite_scaffold_source`,
'gsheet'/'powerschool' modes, the toggle) with a description of the single blend
behavior: PowerSchool-derived grade membership from actual current enrollment,
unioned with sheet rows PowerSchool cannot supply (whole-school `-9` rows,
Miami's full spine, net-new grades/schools), anti-joined on region + schoolid +
grade_level. Update `grade_level` column description: `-9` = whole-school total
row (never PowerSchool-sourced — see `scaffold_source`), else 0–12. Keep the
uniqueness test unchanged.

- [ ] **Step 4: Parse, lint, commit**

```bash
uv run dbt parse --target prod --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/kipptaf
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__enrollment_scaffold.sql \
  src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__enrollment_scaffold.yml \
  src/dbt/kipptaf/dbt_project.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages add \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__enrollment_scaffold.sql \
  src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__enrollment_scaffold.yml \
  src/dbt/kipptaf/dbt_project.yml
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages commit -m "refactor(dbt): collapse enrollment scaffold to blend-only, drop scaffold-source var"
```

---

### Task 5: Whole-school sentinel `-1` to `-9`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__finalsite__school_scaffold.sql`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__finalsite__goals.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__fresh_dashboard_progress_to_goals.sql`
- Modify: yml descriptions that document the `-1` sentinel (grep-driven; at
  minimum `properties/int_finalsite__goals_scaffold.yml`, the two staging ymls,
  `int_google_sheets__finalsite__goals_pivot.yml` if it mentions -1)

**Interfaces:**

- Consumes: the sheets' raw `-1` school-total convention (unchanged in the
  sheets themselves).
- Produces: everywhere downstream of these two staging models, whole-school
  total rows carry `grade_level = -9`. Applicant-side `-1` now unambiguously
  means PK. Verified consumer set of both staging models (checked at PR head):
  `int_finalsite__enrollment_scaffold`, `int_finalsite__goals_scaffold`,
  `int_google_sheets__finalsite__goals_pivot`,
  `rpt_tableau__fresh_dashboard_progress_to_goals`, and the region-mismatch
  singular test — nothing outside the FRESH pipeline.

- [ ] **Step 1: Recode at both sheet staging models**

`stg_google_sheets__finalsite__school_scaffold.sql` — current body selects `*`
plus a `school_level` case. Change to:

```sql
select
    * except (grade_level),

    -- -1 in the sheet means "whole-school total"; recoded to -9 so -1 can
    -- mean PK everywhere downstream (PK = -1, K = 0, 1-12).
    if(grade_level = -1, -9, grade_level) as grade_level,

    case
        when grade_level >= 9
        then 'HS'
        when grade_level >= 5
        then 'MS'
        when grade_level >= 0
        then 'ES'
    end as school_level,

from {{ source("google_sheets", "src_google_sheets__finalsite__school_scaffold") }}
```

(the `school_level` case reads the raw column — negative rows get null
school_level before and after; behavior unchanged.)

`stg_google_sheets__finalsite__goals.sql` — currently
`select *, from {{ source(...) }}`. Change to:

```sql
select
    * except (grade_level),

    -- -1 in the sheet means "whole-school total"; recoded to -9 (see
    -- stg_google_sheets__finalsite__school_scaffold).
    if(grade_level = -1, -9, grade_level) as grade_level,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
```

- [ ] **Step 2: Move the rpt filter/emission sites**

In `rpt_tableau__fresh_dashboard_progress_to_goals.sql`, six sites (PR-head line
numbers 24, 46, 60, 98, 320, 361): `where s.grade_level = -1` → `= -9`;
`where s.grade_level != -1 ...` → `!= -9`; both `-1 as grade_level,` emissions →
`-9 as grade_level,`.

- [ ] **Step 3: Sweep remaining references (SQL, YAML, and md)**

```bash
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages grep -rn -- '-1' \
  src/dbt/kipptaf/models/finalsite src/dbt/kipptaf/models/google/sheets \
  src/dbt/kipptaf/models/extracts/tableau src/dbt/kipptaf/tests | grep -iv 'PK\|prekinder'
```

For every hit that documents or tests the whole-school sentinel, update `-1` →
`-9` (yml descriptions in `int_finalsite__goals_scaffold.yml`, the goals-pivot
yml's "School (whole-school total, grade_level = -1)" text, comments in the
scaffold model if any remain). Do NOT touch `-1` values that mean PK (finalsite
staging decode from Task 1, focus decode from Task 2) or arithmetic like
`syear + 1`. Doc/skill files are Task 6.

- [ ] **Step 4: Validate scaffold output against prod baseline**

Build the recoded chain into dev and compare with prod:

```bash
uv run dbt build --select stg_google_sheets__finalsite__school_scaffold \
  stg_google_sheets__finalsite__goals int_finalsite__enrollment_scaffold \
  int_finalsite__goals_scaffold \
  --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: all build; uniqueness + region-mismatch tests pass. Then via BigQuery
MCP: dev `int_finalsite__enrollment_scaffold` has the same row count as prod's,
zero rows with `grade_level = -1`, and the count of `grade_level = -9` rows
equals prod's count of `-1` rows.

- [ ] **Step 5: Lint changed files, commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__finalsite__school_scaffold.sql \
  src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__finalsite__goals.sql \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__fresh_dashboard_progress_to_goals.sql </dev/null
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages add -u
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages commit -m "refactor(dbt): recode whole-school total sentinel to -9, freeing -1 for PK"
```

---

### Task 6: Minor review fixes + docs/skill rewrite

**Files:**

- Modify: `src/dbt/kipptaf/tests/properties.yml`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__finalsite_student_scaffold.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__finalsite_student_scaffold.yml`
- Modify: `docs/reference/fresh-dashboard-data-model.md`
- Modify: `.claude/skills/fresh-dashboard/SKILL.md`

**Interfaces:**

- Consumes: final state of Tasks 1–5.
- Produces: docs/skill that match the shipped code; no functional model changes
  except comments/yml text.

- [ ] **Step 1: Drop the redundant severity override**

In `src/dbt/kipptaf/tests/properties.yml`, on
`test_int_finalsite__goals_scaffold_region_matches_scaffold`, delete the
`config: severity: warn` block (project default is already `warn`). Keep
`meta.dagster.ref` and the description. Leave the two `severity: error`
overrides on the other tests.

- [ ] **Step 2: Document dedup precedence + fix ps\_\* descriptions**

In `int_tableau__finalsite_student_scaffold.sql`, find the
`dbt_utils.deduplicate` call whose `order_by` is
`"(enroll_status = 0) desc, student_number desc"` (the enrollment-lookup dedup,
NOT the `finalsite_id, grouped_status` one). Immediately above it add:

```sql
-- Cross-source tiebreak: when a student appears in both the frozen
-- pre-migration PowerSchool snapshot and live Focus data with the same
-- enroll_status, student_number desc prefers the Focus record (Focus ids
-- are 10-digit FLDOE-prefixed, PowerSchool ids are shorter) -- intentional:
-- Focus is Miami's live SIS. TODO(#4326) covers duplicate PS records.
```

In the yml, fix `ps_grade_level` / `ps_schoolid` / `ps_school` descriptions:
"from the matched SIS enrollment record (PowerSchool, or Focus for Miami)".

- [ ] **Step 3: Rewrite the stale doc sections**

In `docs/reference/fresh-dashboard-data-model.md`:

1. The "current academic year" section claims the cycle year is "a hardcoded
   literal ... not a column, var, or joined value" with
   `-- finalsite year toggle` markers — replace with: the cycle year is the
   `finalsite_recruitment_year` dbt var in `kipptaf/dbt_project.yml`, read at
   every FRESH site; distinct from `current_academic_year` because SRE's
   recruitment cycle rolls over on its own timeline; update procedure lives in
   the fresh-dashboard skill. Delete the toggle-marker claim and the lineage
   diagram's "hardcoded literal at each model above" line.
1. Scaffold section: describe the single blend implementation (no
   `finalsite_scaffold_source` modes); anti-join keyed on region + schoolid
   - grade_level.
1. Lineage: `stg_finalsite__status_report` transformations (grade decode,
   enrollment_type default) now live in the finalsite PACKAGE model, kipptaf is
   a thin union; `int_focus__student_enrollments` is a kipptaf wrapper over the
   focus package's `int_focus__student_enrollment`; the three `stg_focus__*`
   passthroughs no longer exist.
1. Sentinels: PK = `-1`, whole-school total = `-9` (sheet still says `-1`;
   recoded at the Google-Sheets staging models).

Same four corrections in `.claude/skills/fresh-dashboard/SKILL.md` wherever it
references the var/toggle/mode-switch, the passthroughs, or `-1` school-total.
Verify with:

```bash
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages grep -rn \
  'finalsite_scaffold_source\|year toggle\|hardcoded' -- docs/reference/fresh-dashboard-data-model.md .claude/skills/fresh-dashboard/
```

Expected: no stale hits remain.

- [ ] **Step 4: Lint (markdownlint fires only at CI) and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/tests/properties.yml \
  src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__finalsite_student_scaffold.sql \
  src/dbt/kipptaf/models/extracts/tableau/intermediate/properties/int_tableau__finalsite_student_scaffold.yml \
  docs/reference/fresh-dashboard-data-model.md \
  .claude/skills/fresh-dashboard/SKILL.md </dev/null
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages add -u
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages commit -m "docs: align FRESH reference doc and skill with package refactor"
```

---

### Task 7: Full-graph validation

**Files:** none (verification only)

**Interfaces:**

- Consumes: everything committed in Tasks 1–6.
- Produces: evidence the whole FRESH graph builds and matches prod row counts
  before push.

- [ ] **Step 1: Stage the finalsite package dev copies for all four districts**

The kipptaf status-report wrapper unions four district relations; a kipptaf dev
build resolves each source to `zz_cbini_<district>_finalsite`. Build the package
model in each:

```bash
for d in kippnewark kippcamden kippmiami kipppaterson; do
  uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/$d
  uv run dbt build --select stg_finalsite__status_report \
    --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/$d \
    --target dev --defer --favor-state \
    --state /workspaces/teamster/src/dbt/$d/target/prod
done
```

Expected: four builds pass, including the new `grade_level` `not_null` +
`accepted_values` tests. (Serialize — do not parallelize across projects.)

- [ ] **Step 2: Build the changed kipptaf graph**

```bash
uv run dbt build --select stg_finalsite__status_report+ int_focus__student_enrollments+ \
  int_finalsite__enrollment_scaffold+ stg_google_sheets__finalsite__school_scaffold+ \
  stg_google_sheets__finalsite__goals+ \
  --project-dir /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: full descendant graph (unpivot, scaffolds, student scaffold, both rpt
models, all tests) builds green. Stale-dev caveats from `src/dbt/CLAUDE.md`
apply — before filing any failure as a bug, check the compiled SQL for
`zz_cbini_` refs that shadowed `--favor-state`.

- [ ] **Step 3: Row-count parity vs prod**

Via BigQuery MCP, for `rpt_tableau__fresh_dashboard_aggregated` and
`rpt_tableau__fresh_dashboard_progress_to_goals`: dev row count vs prod row
count at the same moment. Differences must be explainable ONLY by (a)
whole-school rows moving from `-1` to `-9` (count invariant), (b) live warehouse
drift. Any unexplained delta blocks push — diagnose with distinct-key counts per
`src/dbt/CLAUDE.md`.

- [ ] **Step 4: Full lint sweep of the PR diff**

```bash
cd /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages && \
  git diff --name-only --diff-filter=d origin/grangel/feat/claude-fresh-scaffold-swap...HEAD | \
  xargs /workspaces/teamster/.trunk/tools/trunk check --force --no-fix </dev/null
```

Expected: no issues (deleted files are filtered out).

- [ ] **Step 5: Commit any stragglers, then hand off for push**

No commit expected here. STOP before pushing: the push kicks off dbt Cloud CI,
and CI needs the `zz_stg` staging copies refreshed for the package column adds +
new source table — a `--target staging` build recreates shared tables and
requires the USER's direct authorization (see `src/dbt/CLAUDE.md`). Present the
exact commands and wait:

```bash
uv run dbt build --select stg_finalsite__status_report \
  --project-dir <worktree>/src/dbt/<district> --target staging   # x4 districts
uv run dbt build --select int_focus__student_enrollment \
  --project-dir <worktree>/src/dbt/kippmiami --target staging
```

---

### Task 8: Push + stacked PR

**Files:** none (GitHub only)

**Interfaces:**

- Consumes: the completed branch; user authorization for staging builds (Task 7
  Step 5).
- Produces: a PR based on `grangel/feat/claude-fresh-scaffold-swap` with the
  repo PR template body.

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini-refactor-claude-fresh-scaffold-packages push -u origin cbini/refactor/claude-fresh-scaffold-packages
```

(Confirm dbt Cloud has no in-progress run on #4488 first.)

- [ ] **Step 2: Open the PR**

Use `mcp__github__create_pull_request` with
`base: grangel/feat/claude-fresh-scaffold-swap`, head the new branch, title
`refactor(dbt): move FRESH shared models into packages, collapse scaffold`. Body
from `.github/pull_request_template.md`, covering: the three structural changes,
the sentinel scheme (PK `-1` / school-total `-9`), `Refs #4451`, and a
**prominent Tableau coordination note**: SRE must update every workbook
reference of `grade_level = -1` (school-total) to `-9` in sync with this merge.
Note that `claude-review` will NOT run (base is not `main`) and dbt Cloud CI
will. Comment a cross-link on #4488 pointing at the new PR.

- [ ] **Step 3: Verify CI**

Both surfaces: `gh pr checks <n> --json name,bucket,state` (Trunk check runs)
and the dbt Cloud commit status. After dbt Cloud passes, fetch warnings with
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` before
declaring done.

---

## Self-Review Notes

- Spec §1 → Task 4. §2 → Task 1. §3 → Tasks 2–3. §4 → Tasks 1 (PK decode +
  tests), 2 (Focus PK decode), 5 (school-total recode). §5 minors → Tasks 4
  (region anti-join), 6 (doc/skill, severity, dedup comment, ps\_\*
  descriptions), 2 (first-day TODO). §6 tests → Tasks 1, 2, 3, 6. §7 landing →
  Tasks 7–8. Out-of-scope items (Miami blend wiring, qc model, sheet
  conventions) appear in no task — correct.
- `int_focus__student_enrollment` column names in Task 2's Produces block match
  Task 3's wrapper references (`student_enrollment_id`, `academic_year`,
  `schoolid`, `startdate`, `exitdate`, `school_number`, `school_level`,
  `student_number`) — verified consistent.
- Known judgment calls for the executor: `extract_region` macro signature (Task
  3 Step 1 says verify), exact ST06 ordering after edits (trunk is the arbiter),
  and which yml lines carry `-1` sentinel prose (grep-driven, Task 5 Step 3).
