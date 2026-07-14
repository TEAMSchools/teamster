# Paterson Autocomm Extracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend PowerSchool autocomm extracts (students + teachers) to
`kipppaterson` and redirect all districts' autocomm Couchdrop destination to
`data-team/<code_location>/powerschool/autocomm`.

**Architecture:** Replicate the established per-district pattern: thin district
dbt models filter the network-level `kipptaf_extracts` tables by
`code_location`; a Dagster `extracts/` module built from YAML config queries the
district table via `build_bigquery_query_sftp_asset` and uploads to Couchdrop on
a 3am schedule.

**Tech Stack:** dbt (BigQuery), Dagster, `uv`, Couchdrop SFTP.

**Spec:**
`docs/superpowers/specs/2026-07-14-paterson-autocomm-extracts-design.md` (issue
[#4399](https://github.com/TEAMSchools/teamster/issues/4399))

## Global Constraints

- All work happens in the worktree
  `/workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts`
  (branch `cbini/feat/claude-paterson-autocomm-extracts`). Every file path below
  is relative to that root unless absolute. Every git command uses
  `git -C /workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts`.
- dbt commands:
  `uv run dbt <cmd> --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts/src/dbt/kipppaterson`
  — never `uv --directory ... run dbt`.
- New Couchdrop destination path pattern (exact):
  `data-team/<code_location>/powerschool/autocomm` (e.g.
  `data-team/kipppaterson/powerschool/autocomm`).
- Paterson gets students + teachers only — NO `students_iep` model, source table
  entry, config asset, or exposure ref.
- Trunk lint runs at pre-push, not pre-commit: before finishing, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.
- No PII in commits/PR/issue text (row counts and column names are fine).

---

### Task 1: Paterson dbt extracts models

**Files:**

- Create: `src/dbt/kipppaterson/models/extracts/sources.yml`
- Create:
  `src/dbt/kipppaterson/models/extracts/powerschool/rpt_powerschool__autocomm_students.sql`
- Create:
  `src/dbt/kipppaterson/models/extracts/powerschool/rpt_powerschool__autocomm_teachers.sql`
- Create:
  `src/dbt/kipppaterson/models/extracts/powerschool/properties/rpt_powerschool__autocomm_students.yml`
- Create:
  `src/dbt/kipppaterson/models/extracts/powerschool/properties/rpt_powerschool__autocomm_teachers.yml`
- Create: `src/dbt/kipppaterson/models/exposures/powerschool.yml`
- Modify: `src/dbt/kipppaterson/dbt_project.yml` (add `extracts` block under
  `models: kipppaterson:`)

**Interfaces:**

- Consumes: prod tables `kipptaf_extracts.rpt_powerschool__autocomm_students`
  (filter column `code_location`) and
  `kipptaf_extracts.rpt_powerschool__autocomm_teachers` (filter column
  `home_work_location_dagster_code_location`).
- Produces: BigQuery views
  `kipppaterson_extracts.rpt_powerschool__autocomm_students` and
  `kipppaterson_extracts.rpt_powerschool__autocomm_teachers`, with Dagster asset
  keys `kipppaterson/extracts/rpt_powerschool__autocomm_students` and
  `kipppaterson/extracts/rpt_powerschool__autocomm_teachers` (Task 2 depends on
  these exact keys/names).

- [ ] **Step 1: Create `src/dbt/kipppaterson/models/extracts/sources.yml`**

Newark's file minus the IEP table:

```yaml
sources:
  - name: kipptaf_extracts
    tables:
      - name: rpt_powerschool__autocomm_teachers
        config:
          meta:
            dagster:
              group: extracts
              asset_key:
                - kipptaf
                - extracts
                - rpt_powerschool__autocomm_teachers
      - name: rpt_powerschool__autocomm_students
        config:
          meta:
            dagster:
              group: extracts
              asset_key:
                - kipptaf
                - extracts
                - rpt_powerschool__autocomm_students
```

- [ ] **Step 2: Copy the two model SQL files and two properties YAMLs from
      Newark verbatim**

The SQL is identical across NJ districts (`{{ project_name }}` resolves
per-project), and the properties YAMLs carry only column contracts:

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts
mkdir -p "${wt}/src/dbt/kipppaterson/models/extracts/powerschool/properties" \
  "${wt}/src/dbt/kipppaterson/models/exposures"
cp /workspaces/teamster/src/dbt/kippnewark/models/extracts/powerschool/rpt_powerschool__autocomm_students.sql \
  "${wt}/src/dbt/kipppaterson/models/extracts/powerschool/"
cp /workspaces/teamster/src/dbt/kippnewark/models/extracts/powerschool/rpt_powerschool__autocomm_teachers.sql \
  "${wt}/src/dbt/kipppaterson/models/extracts/powerschool/"
cp /workspaces/teamster/src/dbt/kippnewark/models/extracts/powerschool/properties/rpt_powerschool__autocomm_students.yml \
  "${wt}/src/dbt/kipppaterson/models/extracts/powerschool/properties/"
cp /workspaces/teamster/src/dbt/kippnewark/models/extracts/powerschool/properties/rpt_powerschool__autocomm_teachers.yml \
  "${wt}/src/dbt/kipppaterson/models/extracts/powerschool/properties/"
```

For reference, the copied students SQL is:

```sql
select
    student_number,
    student_web_id,
    student_web_password,
    student_allowwebaccess,
    web_id,
    web_password,
    allowwebaccess,
    team,
    track,
    eligibility_name,
    total_balance,
    home_room,
    graduation_year,
    district_entry_date,
    school_entry_date,
    retained_tf,
    s_nj_stu_x__graduation_pathway_math,
    s_nj_stu_x__graduation_pathway_ela,
    u_studentsuserfields__studentemail,
    s_stu_x__fafsa,
from {{ source("kipptaf_extracts", "rpt_powerschool__autocomm_students") }}
where code_location = '{{ project_name }}'
```

and the copied teachers SQL is:

```sql
select
    teachernumber,
    first_name,
    last_name,
    loginid,
    teacherloginid,
    email_addr,
    schoolid,
    homeschoolid,
    `status`,
    teacherldapenabled,
    adminldapenabled,
    ptaccess,
    dob,
    staffstatus,
from {{ source("kipptaf_extracts", "rpt_powerschool__autocomm_teachers") }}
where home_work_location_dagster_code_location = '{{ project_name }}'
```

Verify the copies match those exactly (a mismatch means Newark's models changed
since this plan was written — stop and re-check the spec).

- [ ] **Step 3: Create `src/dbt/kipppaterson/models/exposures/powerschool.yml`**

Newark's exposure minus the IEP ref:

```yaml
exposures:
  - name: powerschool_autocomm
    label: PowerSchool AutoComm
    type: application
    owner:
      name: Data Team
    depends_on:
      - ref("rpt_powerschool__autocomm_students")
      - ref("rpt_powerschool__autocomm_teachers")
    config:
      meta:
        dagster:
          kinds:
            - powerschool
```

- [ ] **Step 4: Add the `extracts` model config to
      `src/dbt/kipppaterson/dbt_project.yml`**

In the `models: kipppaterson:` block, insert `extracts` alphabetically before
`powerschool` (matching Newark's block, which also enforces contracts):

```yaml
models:
  kipppaterson:
    extracts:
      +schema: extracts
      +contract:
        enforced: true
    powerschool: ...existing content unchanged...
```

(Only the `extracts:` key is new; do not touch the rest of the file.)

- [ ] **Step 5: Install packages and parse**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts
uv run dbt deps --project-dir "${wt}/src/dbt/kipppaterson"
uv run dbt parse --project-dir "${wt}/src/dbt/kipppaterson"
```

Expected: parse completes with no errors (warnings about unrelated models are
pre-existing).

- [ ] **Step 6: Build both models into the dev schema**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts
uv run dbt build \
  --select rpt_powerschool__autocomm_students rpt_powerschool__autocomm_teachers \
  --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipppaterson/target/prod \
  --project-dir "${wt}/src/dbt/kipppaterson"
```

Expected: 2 models PASS. If `--state` fails with "Could not find manifest",
regenerate the main repo's prod manifest:
`uv run dbt parse --target prod --project-dir /workspaces/teamster/src/dbt/kipppaterson --target-path target/prod`.

- [ ] **Step 7: Spot-check row counts against the network tables**

Query via BigQuery MCP (dev schema is `zz_cbini_kipppaterson_extracts`):

```sql
select
    (
        select count(*)
        from zz_cbini_kipppaterson_extracts.rpt_powerschool__autocomm_students
    ) as students_dev,
    (
        select count(*)
        from kipptaf_extracts.rpt_powerschool__autocomm_students
        where code_location = 'kipppaterson'
    ) as students_network,
    (
        select count(*)
        from zz_cbini_kipppaterson_extracts.rpt_powerschool__autocomm_teachers
    ) as teachers_dev,
    (
        select count(*)
        from kipptaf_extracts.rpt_powerschool__autocomm_teachers
        where home_work_location_dagster_code_location = 'kipppaterson'
    ) as teachers_network
```

Expected: `students_dev = students_network` and
`teachers_dev = teachers_network`, both nonzero (553 / 91 at design time; live
counts may drift slightly).

- [ ] **Step 8: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts
git -C "${wt}" add src/dbt/kipppaterson
git -C "${wt}" commit -m "feat: add Paterson powerschool autocomm extract models

Refs #4399

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Paterson Dagster extracts module

**Files:**

- Create: `src/teamster/code_locations/kipppaterson/extracts/__init__.py`
- Create: `src/teamster/code_locations/kipppaterson/extracts/assets.py`
- Create: `src/teamster/code_locations/kipppaterson/extracts/jobs.py`
- Create: `src/teamster/code_locations/kipppaterson/extracts/schedules.py`
- Create:
  `src/teamster/code_locations/kipppaterson/extracts/config/powerschool.yaml`
- Modify: `src/teamster/code_locations/kipppaterson/definitions.py`
- Modify: `src/teamster/code_locations/kipppaterson/CLAUDE.md`

**Interfaces:**

- Consumes: dbt asset keys
  `kipppaterson/extracts/rpt_powerschool__autocomm_students` and
  `kipppaterson/extracts/rpt_powerschool__autocomm_teachers` from Task 1 (the
  factory derives each dep from the config's `query_config.value.table.name`);
  `build_bigquery_query_sftp_asset(code_location, timezone, query_config, file_config, destination_config)`
  from `teamster.libraries.extracts.assets`; `BIGQUERY_RESOURCE` from
  `teamster.core.resources`.
- Produces: assets keyed
  `kipppaterson/extracts/couchdrop/powerschool_autocomm_students_txt` and
  `kipppaterson/extracts/couchdrop/powerschool_autocomm_teachers_accounts_txt`;
  job `kipppaterson__extracts__powerschool__asset_job`; a 3am America/New_York
  schedule.

- [ ] **Step 1: Create
      `src/teamster/code_locations/kipppaterson/extracts/config/powerschool.yaml`**

```yaml
assets:
  - query_config:
      type: schema
      value:
        table:
          schema: kipppaterson_extracts
          name: rpt_powerschool__autocomm_teachers
    file_config:
      stem: powerschool_autocomm_teachers_accounts
      suffix: txt
      format:
        delimiter: "\t"
        header: False
    destination_config:
      name: couchdrop
      path: data-team/kipppaterson/powerschool/autocomm
  - query_config:
      type: schema
      value:
        table:
          schema: kipppaterson_extracts
          name: rpt_powerschool__autocomm_students
    file_config:
      stem: powerschool_autocomm_students
      suffix: txt
      format:
        delimiter: "\t"
        header: False
    destination_config:
      name: couchdrop
      path: data-team/kipppaterson/powerschool/autocomm
```

- [ ] **Step 2: Create
      `src/teamster/code_locations/kipppaterson/extracts/assets.py`**

```python
import pathlib

from dagster import config_from_files

from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.extracts.assets import build_bigquery_query_sftp_asset

config_dir = pathlib.Path(__file__).parent / "config"

powerschool_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/powerschool.yaml"])["assets"]
]

assets = [
    *powerschool_extract_assets,
]
```

- [ ] **Step 3: Create
      `src/teamster/code_locations/kipppaterson/extracts/jobs.py`**

```python
from dagster import define_asset_job

from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.code_locations.kipppaterson.extracts.assets import (
    powerschool_extract_assets,
)

powerschool_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__powerschool__asset_job",
    selection=powerschool_extract_assets,
)
```

- [ ] **Step 4: Create
      `src/teamster/code_locations/kipppaterson/extracts/schedules.py`**

```python
from dagster import ScheduleDefinition

from teamster.code_locations.kipppaterson import LOCAL_TIMEZONE
from teamster.code_locations.kipppaterson.extracts.jobs import (
    powerschool_extract_asset_job,
)

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_asset_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    powerschool_extract_assets_schedule,
]
```

- [ ] **Step 5: Create
      `src/teamster/code_locations/kipppaterson/extracts/__init__.py`**

```python
from teamster.code_locations.kipppaterson.extracts.assets import assets
from teamster.code_locations.kipppaterson.extracts.schedules import schedules

__all__ = [
    "assets",
    "schedules",
]
```

- [ ] **Step 6: Wire into
      `src/teamster/code_locations/kipppaterson/definitions.py`**

Four edits (keep alphabetical ordering):

1. Add `extracts,` to the `teamster.code_locations.kipppaterson` import list
   (after `deanslist`, before `finalsite`):

   ```python
   from teamster.code_locations.kipppaterson import (
       CODE_LOCATION,
       DBT_PROJECT,
       amplify,
       couchdrop,
       dbt,
       deanslist,
       extracts,
       finalsite,
       pearson,
       powerschool,
   )
   ```

2. Add `BIGQUERY_RESOURCE,` to the `teamster.core.resources` import list (first
   entry, before `DEANSLIST_RESOURCE`).

3. Add `extracts,` to the `load_assets_from_modules` list (after `deanslist`,
   before `finalsite`) and add its schedules:

   ```python
       assets=load_assets_from_modules(
           modules=[
               dbt,
               amplify,
               deanslist,
               extracts,
               finalsite,
               pearson,
               powerschool,
           ]
       ),
       schedules=[
           *deanslist.schedules,
           *extracts.schedules,
           *finalsite.schedules,
       ],
   ```

4. Add the BigQuery resource to the resources dict (before `"dbt_cli"`):

   ```python
       resources={
           "db_bigquery": BIGQUERY_RESOURCE,
           "dbt_cli": get_dbt_cli_resource(DBT_PROJECT),
           ...existing entries unchanged...
       },
   ```

- [ ] **Step 7: Validate the module imports**

Full `definitions` import is expected to work for Paterson (it has no
PowerSchool ODBC resource), but the repo-standard check is the submodule:

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts
VIRTUAL_ENV= uv --directory "${wt}" run python -c "
from teamster.code_locations.kipppaterson import extracts
assert len(extracts.assets) == 2, extracts.assets
assert len(extracts.schedules) == 1
keys = sorted(a.key.to_user_string() for a in extracts.assets)
print(keys)
assert keys == [
    'kipppaterson/extracts/couchdrop/powerschool_autocomm_students_txt',
    'kipppaterson/extracts/couchdrop/powerschool_autocomm_teachers_accounts_txt',
], keys
print('OK')
"
```

Expected: prints the two asset keys and `OK`. (IDE Pyright errors on worktree
files are false positives — trust this command.)

- [ ] **Step 8: Update `src/teamster/code_locations/kipppaterson/CLAUDE.md`**

Three edits:

1. Add a row to the Active Integrations table (after `pearson`):

   ```markdown
   | `extracts` | BigQuery→SFTP | schedule (3am) |
   ```

2. In the "Critical Difference: PowerSchool via SFTP" consequences list, replace
   the two now-false bullets. The list currently reads:

   ```markdown
   - No `db_powerschool` or `ssh_powerschool` resources in `definitions.py`
   - No `db_bigquery` resource (no BigQuery writes from this location)
   - No extracts module (no BigQuery to query)
   - No `edplan`, `iready`, `overgrad`, `renlearn`, or `titan`
   ```

   Replace with:

   ```markdown
   - No `db_powerschool` or `ssh_powerschool` resources in `definitions.py`
   - `db_bigquery` exists only for the `extracts` module (PowerSchool autocomm);
     ingestion still writes no BigQuery data from this location
   - No `edplan`, `iready`, `overgrad`, `renlearn`, or `titan`
   ```

3. In the Schedules paragraph, change "DeansList and Finalsite `contacts` add
   nightly data-pull schedules" to "DeansList, Finalsite `contacts`, and the
   PowerSchool autocomm `extracts` job add nightly schedules".

- [ ] **Step 9: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts
git -C "${wt}" add src/teamster/code_locations/kipppaterson
git -C "${wt}" commit -m "feat: add Paterson powerschool autocomm extracts module

Refs #4399

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Redirect Couchdrop destination paths for existing districts

**Files:**

- Modify:
  `src/teamster/code_locations/kippnewark/extracts/config/powerschool.yaml` (3
  `path:` lines)
- Modify:
  `src/teamster/code_locations/kippcamden/extracts/config/powerschool.yaml` (3
  `path:` lines)
- Modify:
  `src/teamster/code_locations/kippmiami/extracts/config/powerschool.yaml` (2
  `path:` lines)

**Interfaces:**

- Consumes: nothing from other tasks (independent config edit).
- Produces: every autocomm `destination_config.path` set to
  `data-team/<code_location>/powerschool/autocomm`. Paterson's config (Task 2)
  already uses the new pattern.

- [ ] **Step 1: Edit the three config files**

In each file, replace every occurrence:

- kippnewark: `path: teamster-kippnewark/couchdrop/powerschool` →
  `path: data-team/kippnewark/powerschool/autocomm` (3 occurrences)
- kippcamden: `path: teamster-kippcamden/couchdrop/powerschool` →
  `path: data-team/kippcamden/powerschool/autocomm` (3 occurrences)
- kippmiami: `path: teamster-kippmiami/couchdrop/powerschool` →
  `path: data-team/kippmiami/powerschool/autocomm` (2 occurrences)

These files contain nothing but the autocomm assets, so a whole-file replacement
is safe.

- [ ] **Step 2: Verify no old autocomm paths remain**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts
grep -rn "couchdrop/powerschool" "${wt}/src/teamster/code_locations/"
```

Expected: no output. Then confirm the new paths:

```bash
grep -rn "data-team/" "${wt}/src/teamster/code_locations/"
```

Expected: 10 `path:` lines across the four districts' extract configs (3
Newark + 3 Camden + 2 Miami + 2 Paterson).

- [ ] **Step 3: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts
git -C "${wt}" add src/teamster/code_locations/kippnewark/extracts/config/powerschool.yaml \
  src/teamster/code_locations/kippcamden/extracts/config/powerschool.yaml \
  src/teamster/code_locations/kippmiami/extracts/config/powerschool.yaml
git -C "${wt}" commit -m "feat: redirect powerschool autocomm extracts to data-team couchdrop folder

Refs #4399

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Lint and final verification

**Files:**

- No new files; verifies the branch is push-clean.

**Interfaces:**

- Consumes: all commits from Tasks 1–3.
- Produces: a lint-clean branch ready for PR (PR creation is handled by the
  finishing-a-development-branch flow, not this plan).

- [ ] **Step 1: Trunk-check every changed file**

sqlfluff/yamllint only fire at pre-push/CI, so check now:

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts
git diff --name-only main...HEAD | grep -v '^docs/' \
  | xargs /workspaces/teamster/.trunk/tools/trunk check --force --no-fix </dev/null
```

Expected: `No issues`. If formatting issues appear, run
`/workspaces/teamster/.trunk/tools/trunk fmt <files> </dev/null` (same cwd),
re-check, and amend the relevant commit.

- [ ] **Step 2: Re-run the import validation from Task 2 Step 7**

Same command; expected same `OK` output (guards against Task 3 typos in YAML).

- [ ] **Step 3: Re-run dbt parse**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts
uv run dbt parse --project-dir "${wt}/src/dbt/kipppaterson"
```

Expected: no errors.

- [ ] **Step 4: Commit any lint fixes**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-paterson-autocomm-extracts
git -C "${wt}" status --short
```

If clean, done. If lint produced changes, stage the specific files it touched
and commit with message `style: apply trunk formatting` (+ the `Refs #4399` /
`Co-Authored-By` lines as in prior commits).

---

## Post-merge (not part of this branch)

- Coordinate with the PowerSchool AutoComm owner to repoint imports at
  `data-team/<code_location>/powerschool/autocomm` before/at merge.
- After the post-merge location deploys, confirm the 3am schedule run uploads
  both Paterson files and existing districts' files land under `data-team/`.
