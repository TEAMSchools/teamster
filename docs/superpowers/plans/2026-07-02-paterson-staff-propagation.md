# Paterson Staff Propagation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Propagate Paterson (`KPAT`) staff through the ADP-sourced staff roster
and downstream extracts by removing the spine exclusion filter and the
PowerSchool-direct re-injection workarounds.

**Architecture:** One dbt exclusion in `int_people__staff_roster_history`
currently drops Paterson before it reaches `int_people__staff_roster`. Removing
it propagates Paterson into ~50 ADP-derived extracts automatically. Three
PowerSchool-sourced extracts (`rpt_illuminate__users`, `rpt_illuminate__roles`,
`rpt_clever__staff`) carry compensating workarounds that must be removed in the
same PR to avoid duplicate/mis-keyed rows once Paterson enters the roster.

**Tech Stack:** dbt (BigQuery), `kipptaf` project. SQL only — no Python.

## Global Constraints

- **Single PR**, held until three Ops gates land in prod (crosswalk populate,
  Zendesk re-key re-verify, LDAP `TMP` update). See the design spec:
  `docs/superpowers/specs/2026-06-22-paterson-staff-propagation-design.md`.
- **Worktree:** all work happens in
  `/workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation`
  (branch `cbini/feat/claude-paterson-staff-propagation`). Use
  `git -C <worktree>` for git and `--project-dir <worktree>/src/dbt/kipptaf` for
  dbt. Never run bare `git`/`dbt` from the main repo.
- **dbt local runs:** `--target dev` with
  `--defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod` (absolute
  path — required from a worktree). `--target prod` is classifier-blocked; hand
  prod builds to the user. `dbt compile`/`parse` are never blocked.
- **SQL style** (`.trunk/config/.sqlfluff`): BigQuery dialect, single quotes,
  trailing commas in `SELECT`, 88-char lines, no `ORDER BY`, no `SELECT *` in
  final `rpt_` selects. Do not run `trunk fmt`/`check` manually except the
  explicit `trunk check` step (pre-commit runs fmt; pre-push runs the rest).
- **No new duplication idioms:** do not add `select distinct`,
  `qualify row_number()=1`, or `dbt_utils.deduplicate` anywhere in this work.
  The changes are filter removals plus one additive union branch.
- **Verification split:** the spine + non-SIS extracts (Coupa/Egencia/Zendesk)
  are verifiable locally now; the SIS-coupled models (`rpt_illuminate__*`,
  `rpt_clever__staff`) fully verify only after the crosswalk + Zendesk Ops gates
  land in staging (Task 6).

---

## Task 0: Worktree sync and dbt deps

**Files:** none (environment setup).

- [ ] **Step 1: Merge latest main into the branch**

Run:

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation fetch origin main
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation merge origin/main
```

Expected: clean merge (branch only holds the design spec + this plan).

- [ ] **Step 2: Install dbt packages in the worktree**

Run:

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf
```

Expected: `Installed from ...` for each package; no errors. (A fresh worktree
has no `dbt_packages/`.)

- [ ] **Step 3: Confirm the prod manifest exists for `--defer`**

Run:

```bash
ls /workspaces/teamster/src/dbt/kipptaf/target/prod/manifest.json
```

Expected: the file exists. If missing, regenerate:
`uv run dbt parse --target prod --project-dir /workspaces/teamster/src/dbt/kipptaf --target-path target/prod`.

---

## Task 1: Remove the ADP spine Paterson filter

**Files:**

- Modify:
  `src/dbt/kipptaf/models/people/intermediate/int_people__staff_roster_history.sql`
  (the `where` clause of the ADP Workforce Now branch, ~lines 114-119)

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: Paterson rows in `int_people__staff_roster_history` and
  `int_people__staff_roster`. Downstream tasks and every ADP-derived extract
  rely on Paterson being present in `int_people__staff_roster`.

- [ ] **Step 1: Baseline — confirm Paterson is absent today**

Run:

```bash
uv run dbt compile --project-dir /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select int_people__staff_roster
```

Then query prod (BigQuery MCP or `bq`):

```sql
select count(*) as paterson_rows
from `teamster-332318.kipptaf_people.int_people__staff_roster`
where home_business_unit_name = 'KIPP Paterson';
```

Expected: `paterson_rows = 0` (baseline — filter still in place upstream).

- [ ] **Step 2: Edit the `where` clause**

In `int_people__staff_roster_history.sql`, replace:

```sql
        where
            w.effective_date_end >= '2021-01-01'
            and coalesce(w.organizational_unit__home__business_unit__name, '')
            != 'KIPP Paterson'
            and coalesce(w.organizational_unit__assigned__business_unit__name, '')
            != 'KIPP Paterson'
```

with:

```sql
        where w.effective_date_end >= '2021-01-01'
```

- [ ] **Step 3: Compile to validate SQL/refs**

Run:

```bash
uv run dbt compile --project-dir /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select int_people__staff_roster_history
```

Expected: `Compiled node 'int_people__staff_roster_history'`; no errors.

- [ ] **Step 4: Build the roster into dev and check the grain**

Run:

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select int_people__staff_roster_history int_people__staff_roster
```

Expected: both models build; uniqueness test on `int_people__staff_roster`
PASSES (no Paterson-driven duplication).

- [ ] **Step 5: Verify Paterson now propagates (~94 staff)**

Query the dev schema (`zz_cbini_kipptaf_people`):

```sql
select count(distinct employee_number) as paterson_staff
from `teamster-332318.zz_cbini_kipptaf_people.int_people__staff_roster`
where home_business_unit_name = 'KIPP Paterson';
```

Expected: `paterson_staff` ≈ 94 (current Paterson active/current-record
workers).

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation add src/dbt/kipptaf/models/people/intermediate/int_people__staff_roster_history.sql
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation commit -m "feat(kipptaf): remove Paterson exclusion from staff roster spine"
```

---

## Task 2: Remove the Illuminate users PS-direct Paterson branch

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__users.sql`
  (delete the `stg_powerschool__users` union branch, ~lines 15-32)

**Interfaces:**

- Consumes: Paterson present in `int_people__staff_roster` (Task 1).
- Produces: `rpt_illuminate__users` with Paterson teachers sourced only from the
  roster branch; `01 User ID` = `powerschool_teacher_number`.

- [ ] **Step 1: Edit — delete the PS-direct union branch**

In `rpt_illuminate__users.sql`, delete this entire block (the middle `union all`
branch), leaving the `int_people__staff_roster` branch and the
`int_people__temp_staff` branch intact:

```sql
        union all

        select
            null as employee_number,

            teachernumber as powerschool_teacher_number,
            last_name as family_name_1,
            first_name as given_name,
            email_addr as user_principal_name,
            email_addr as sam_account_name,

            if(ptaccess = 1 or psaccess = 1, 0, 2) as uac_account_disable,

            'KIPP Paterson' as home_business_unit_name,

            title as job_title,
        from {{ ref("stg_powerschool__users") }}
        where _dbt_source_relation like '%kipppaterson%'
```

- [ ] **Step 2: Compile to validate**

Run:

```bash
uv run dbt compile --project-dir /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select rpt_illuminate__users
```

Expected: compiles clean; the compiled SQL no longer references
`stg_powerschool__users`.

- [ ] **Step 3: Confirm no stray `stg_powerschool__users` ref remains**

Run:

```bash
grep -n "stg_powerschool__users\|kipppaterson\|KIPP Paterson" \
  /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__users.sql
```

Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation add src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__users.sql
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation commit -m "feat(kipptaf): drop Illuminate PS-direct Paterson user branch"
```

> Full data-test verification (unique `01 User ID`, teacher-number match to
> `mastschd`/`roster`) runs in Task 6 after the crosswalk gate lands.

---

## Task 3: Rework the Illuminate roles Paterson branch

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__roles.sql`
  (remove the PS-direct Paterson branch; add a Paterson region-wide branch;
  guard the school-based branch)

**Interfaces:**

- Consumes: Paterson present in `int_people__staff_roster` (Task 1), with
  `home_business_unit_name = 'KIPP Paterson'`,
  `home_work_location_powerschool_school_id`, `worker_status_code`,
  `powerschool_teacher_number`.
- Produces: `rpt_illuminate__roles` where Paterson regional/CMO staff
  (`school_id = 0`) get "School Leadership" roles at all Paterson schools
  (`school_number` 2 and 1234), and school-based Paterson staff get their home
  school — with no Paterson `Site ID = 0` rows.

- [ ] **Step 1: Delete the PS-direct Paterson branch**

In `rpt_illuminate__roles.sql`, delete this `union all` branch (the "Paterson =
all schools in region" block reading `stg_powerschool__users`):

```sql
union all

/* Paterson = all schools in region */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    u.teachernumber as `01 Local User ID`,

    s.school_number as `02 Site ID`,

    'School Leadership' as `03 Role Name`,

    concat(
        {{ current_school_year(var("local_timezone")) }},
        '-',
        {{ current_school_year(var("local_timezone")) }} + 1
    ) as `04 Academic Year`,

    1 as `05 Session Type ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("stg_powerschool__users") }} as u
inner join
    {{ ref("stg_powerschool__schools") }} as s
    on {{ union_dataset_join_clause(left_alias="u", right_alias="s") }}
    and s.state_excludefromreporting = 0
where
    u._dbt_source_relation like '%kipppaterson%' and (u.ptaccess = 1 or u.psaccess = 1)
```

- [ ] **Step 2: Guard the school-based branch against Paterson `Site ID = 0`**

Find the school-based branch
(`/* School-based staff = only respective school */`). Its `where` clause
currently reads:

```sql
where
    worker_status_code != 'Terminated'
    and home_department_name not in ('Teaching and Learning', 'Data', 'Executive')
    and not home_work_location_is_campus
```

Add a Paterson-scoped guard so Paterson `school_id = 0` staff are excluded (they
are handled by the new branch in Step 3):

```sql
where
    worker_status_code != 'Terminated'
    and home_department_name not in ('Teaching and Learning', 'Data', 'Executive')
    and not home_work_location_is_campus
    and not (
        home_business_unit_name = 'KIPP Paterson'
        and home_work_location_powerschool_school_id = 0
    )
```

> The 57 pre-existing non-Paterson `Site ID = 0` rows are out of scope — do not
> broaden the guard beyond Paterson.

- [ ] **Step 3: Add the Paterson region-wide branch**

Append this branch to the end of the model (after the existing `/* Temps */`
branch):

```sql
union all

/* Paterson regional/CMO staff = all Paterson schools */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    sr.powerschool_teacher_number as `01 Local User ID`,

    s.school_number as `02 Site ID`,

    'School Leadership' as `03 Role Name`,

    concat(
        {{ current_school_year(var("local_timezone")) }},
        '-',
        {{ current_school_year(var("local_timezone")) }} + 1
    ) as `04 Academic Year`,

    1 as `05 Session Type ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_people__staff_roster") }} as sr
inner join
    {{ ref("stg_powerschool__schools") }} as s
    on s.state_excludefromreporting = 0
    and s._dbt_source_relation like '%kipppaterson%'
where
    sr.worker_status_code != 'Terminated'
    and sr.home_business_unit_name = 'KIPP Paterson'
    and sr.home_work_location_powerschool_school_id = 0
```

- [ ] **Step 4: Compile to validate**

Run:

```bash
uv run dbt compile --project-dir /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select rpt_illuminate__roles
```

Expected: compiles clean; no `stg_powerschool__users` reference remains in the
compiled SQL.

- [ ] **Step 5: Confirm the PS-direct branch is gone**

Run:

```bash
grep -n "stg_powerschool__users\|ptaccess\|psaccess" \
  /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__roles.sql
```

Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation add src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__roles.sql
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation commit -m "feat(kipptaf): route Illuminate Paterson roles through the roster"
```

> The unique-combination data test and the "no Paterson `Site ID = 0`" /
> "school_id=0 staff assigned to schools 2 and 1234" checks run in Task 6 after
> the crosswalk gate lands.

---

## Task 4: Remove the Clever staff Paterson schools exclusion

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/clever/rpt_clever__staff.sql` (the
  `schools` CTE `where` clause)

**Interfaces:**

- Consumes: Paterson present in `int_people__staff_roster` (Task 1); Paterson
  `powerschool_school_id` present in `int_people__location_crosswalk` (verified:
  Prep Elementary 1234, Prep Middle 2, Room 12/Room 9 → 0).
- Produces: `rpt_clever__staff` with Paterson schools assignable, so Paterson
  staff resolve to schools via the existing assignment branches.

- [ ] **Step 1: Edit the `schools` CTE**

In `rpt_clever__staff.sql`, replace:

```sql
        where
            state_excludefromreporting = 0
            and _dbt_source_relation not like '%kipppaterson%'
```

with:

```sql
        where state_excludefromreporting = 0
```

- [ ] **Step 2: Compile to validate**

Run:

```bash
uv run dbt compile --project-dir /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select rpt_clever__staff
```

Expected: compiles clean.

- [ ] **Step 3: Confirm the exclusion is gone**

Run:

```bash
grep -n "kipppaterson" \
  /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf/models/extracts/clever/rpt_clever__staff.sql
```

Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation add src/dbt/kipptaf/models/extracts/clever/rpt_clever__staff.sql
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation commit -m "feat(kipptaf): allow Paterson schools in Clever staff assignments"
```

---

## Task 5: Local verification of the spine + non-SIS extracts

**Files:** none (verification only).

**Interfaces:**

- Consumes: all edits from Tasks 1-4.

- [ ] **Step 1: Lint the changed SQL**

Run (from inside the worktree, per repo convention):

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation && \
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/people/intermediate/int_people__staff_roster_history.sql \
  src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__users.sql \
  src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__roles.sql \
  src/dbt/kipptaf/models/extracts/clever/rpt_clever__staff.sql
```

Expected: `✔ No issues` (sqlfluff clean).

- [ ] **Step 2: Build + test the non-SIS extracts that are crosswalk-ready now**

Run:

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev \
  --select rpt_coupa__users rpt_egencia__users
```

Expected: both build; contract + uniqueness tests PASS.

- [ ] **Step 3: Verify Coupa resolves non-NULL Intacct coding for Paterson**

Query the dev schema:

```sql
select
  countif(`Sage Intacct Fund` is null) as null_fund,
  countif(`School Name` is null) as null_school,
  count(*) as paterson_rows
from `teamster-332318.zz_cbini_kipptaf_extracts.rpt_coupa__users`
where `Employee Number` in (
  select cast(employee_number as string)
  from `teamster-332318.zz_cbini_kipptaf_people.int_people__staff_roster`
  where home_business_unit_name = 'KIPP Paterson'
);
```

Expected: `null_fund = 0`, `null_school = 0` (Coupa crosswalks cover Paterson).

- [ ] **Step 4: Verify Egencia never NULLs the traveler group**

```sql
select countif(`Traveler Group` is null) as null_group
from `teamster-332318.zz_cbini_kipptaf_extracts.rpt_egencia__users`;
```

Expected: `null_group = 0` (the `'General Traveler Group'` fallback guarantees
this).

---

## Task 6: Pre-merge gate verification, PR-description mapping table, and PR

**Files:** none (runs after the three Ops gates land in prod; produces the PR).

**Interfaces:**

- Consumes: all edits (Tasks 1-4); the three Ops gates satisfied (crosswalk
  populated, Zendesk re-keyed, LDAP `TMP` updated).

- [ ] **Step 1: Refresh staging for the edited Google Sheets sources**

Ask the user to run (classifier-blocked for the agent; `--target staging`
full-refresh recreates shared `zz_stg_*` tables):

```bash
uv run dbt run-operation stage_external_sources --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf \
  --args '{select: google_sheets.src_google_sheets__people__powerschool_crosswalk google_sheets.src_google_sheets__zendesk_org_lookup, ext_full_refresh: true}'
```

Then rebuild the two staging models:

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf \
  --target staging \
  --select stg_google_sheets__people__powerschool_crosswalk stg_google_sheets__zendesk_org_lookup
```

Expected: both staging tables rebuilt with Paterson rows.

- [ ] **Step 2: Verify the Zendesk join now resolves for Paterson**

```sql
with pat as (
  select distinct sr.home_business_unit_code, sr.home_work_location_reporting_name
  from `teamster-332318.zz_stg_kipptaf_people.int_people__staff_roster` sr
  where sr.home_business_unit_name = 'KIPP Paterson'
)
select pat.home_work_location_reporting_name,
       if(zol.zendesk_organization is null, 'NO MATCH', zol.zendesk_organization) as org
from pat
left join `teamster-332318.zz_stg_kipptaf_google_sheets.stg_google_sheets__zendesk_org_lookup` zol
  on pat.home_business_unit_code = zol.adp_business_unit
  and pat.home_work_location_reporting_name = zol.location_clean_name;
```

Expected: every Paterson work location returns a non-NULL org (no `NO MATCH`).
If Room 9 shows `NO MATCH`, flag to Ops (spec gate 2).

- [ ] **Step 3: Verify Illuminate teacher-number resolution and User-ID match**

Build the SIS models against staging, then confirm the Illuminate `01 User ID`
matches the PS `teachernumber` used by `mastschd`/`roster`:

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation/src/dbt/kipptaf \
  --target staging \
  --select rpt_illuminate__users rpt_illuminate__roles rpt_clever__staff
```

Expected: all build; `unique` on `rpt_illuminate__users.01 User ID` and
`unique_combination_of_columns` on `rpt_illuminate__roles` PASS. Then:

```sql
-- Paterson Illuminate users whose User ID is NOT referenced by any Paterson section/roster
select count(*) as orphaned_paterson_teachers
from `teamster-332318.zz_stg_kipptaf_extracts.rpt_illuminate__users` u
where u.`18 City` = 'KIPP Paterson'
  and u.`01 User ID` not in (
    select cast(`05 User ID` as string)
    from `teamster-332318.zz_stg_kipptaf_extracts.rpt_illuminate__mastschd`
  );
```

Expected: `orphaned_paterson_teachers` is 0 for teachers who own sections
(non-teaching Paterson staff legitimately have no sections — spot-check any
nonzero result against the crosswalk coverage count).

- [ ] **Step 4: Verify the roles region-wide branch and the `Site ID = 0`
      guard**

```sql
-- Paterson school_id=0 staff should have rows for BOTH Paterson schools (2, 1234), none at Site ID 0
select `02 Site ID` as site_id, count(*) as n
from `teamster-332318.zz_stg_kipptaf_extracts.rpt_illuminate__roles`
where `01 Local User ID` in (
  select powerschool_teacher_number
  from `teamster-332318.zz_stg_kipptaf_people.int_people__staff_roster`
  where home_business_unit_name = 'KIPP Paterson'
    and home_work_location_powerschool_school_id = 0
)
group by 1 order by 1;
```

Expected: rows at `site_id` 2 and 1234; **no** row at `site_id` 0.

- [ ] **Step 5: Generate the PR-description crosswalk mapping table**

Run this against the staging build and capture the output for the PR body
(config-level, deidentified — safe to publish):

```sql
select distinct
  sr.home_business_unit_code,
  sr.home_business_unit_name,
  sr.home_work_location_reporting_name,
  sr.home_department_name,
  sr.job_title,
  cu.`School Name` as coupa_school_name,
  cu.`Sage Intacct Fund` as coupa_fund,
  cu.`Sage Intacct Program` as coupa_program,
  cu.`Sage Intacct Department` as coupa_department,
  cu.`Sage Intacct Location` as coupa_location,
  cu.`Default Address Name` as coupa_address,
  eu.`Traveler Group` as egencia_group,
  zu.organization_id as zendesk_org
from `teamster-332318.zz_stg_kipptaf_people.int_people__staff_roster` sr
left join `teamster-332318.zz_stg_kipptaf_extracts.rpt_coupa__users` cu
  on cast(sr.employee_number as string) = cu.`Employee Number`
left join `teamster-332318.zz_stg_kipptaf_extracts.rpt_egencia__users` eu
  on sr.employee_number = eu.`Employee ID`
left join `teamster-332318.zz_stg_kipptaf_extracts.rpt_zendesk__users` zu
  on cast(sr.employee_number as string) = zu.external_id
where sr.home_business_unit_name = 'KIPP Paterson';
```

Also capture the PowerSchool crosswalk coverage count (do NOT list
employee-level pairs — PII):

```sql
select
  count(distinct sr.employee_number) as paterson_staff,
  count(distinct xw.employee_number) as mapped_in_crosswalk
from `teamster-332318.zz_stg_kipptaf_people.int_people__staff_roster` sr
left join `teamster-332318.zz_stg_kipptaf_google_sheets.stg_google_sheets__people__powerschool_crosswalk` xw
  on cast(sr.employee_number as string) = cast(xw.employee_number as string) and xw.is_active
where sr.home_business_unit_name = 'KIPP Paterson';
```

Expected: the mapping table has no NULLs in Coupa/Egencia/Zendesk columns;
report `mapped_in_crosswalk / paterson_staff` as the coverage line.

- [ ] **Step 6: Push and open the PR**

Run (bundle all commits into one push):

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-paterson-staff-propagation push -u origin cbini/feat/claude-paterson-staff-propagation
```

Open the PR with `mcp__github__create_pull_request` using
`.github/pull_request_template.md` as the body, `Closes #4239`, and the mapping
table + coverage line from Step 5. Squash merge.

- [ ] **Step 7: Confirm CI green + warnings**

After dbt Cloud CI reaches a terminal state, check the run status and fetch
warnings with `mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)`.
Confirm no new uniqueness/contract/not-null failures introduced by Paterson rows
before requesting merge.

---

## Self-Review

- **Spec coverage:** spine removal (Task 1) ✓; Illuminate users branch (Task 2)
  ✓; Illuminate roles branch + region-wide decision (Task 3) ✓; Clever schools
  exclusion (Task 4) ✓; Lattice / temp_staff / Coupa / Egencia / Zendesk
  no-code-change (verified in Tasks 5-6) ✓; blast radius (Task 5 spot-checks +
  Task 7 CI) ✓; three Ops gates (Task 6) ✓; PR-description mapping table + PII
  carve-out (Task 6 Step 5) ✓.
- **Placeholders:** none — every edit shows exact before/after SQL and every
  verification step has a concrete command with expected output.
- **Type/name consistency:** `home_business_unit_name`,
  `home_work_location_powerschool_school_id`, `powerschool_teacher_number`,
  `school_number`, `state_excludefromreporting`, `_dbt_source_relation` used
  consistently across Tasks 1, 3, 4, 6, matching the read models.
