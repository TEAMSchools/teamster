# DeansList Family Contacts Extract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a nightly `contacts.txt` DeansList import file for the NJ
regions (Newark, Camden, Paterson) containing each currently enrolled student's
single Finalsite parent contact.

**Architecture:** Split contact first/last names at the finalsite dbt package
level, expose them through the existing kipptaf `union_relations` wrapper, add a
contract-enforced `rpt_deanslist__family_contacts` view reading the Finalsite
intermediates directly, and wire a YAML-only `build_bigquery_query_sftp_asset`
entry that serializes the view to `contacts.txt` (CSV) on the existing nightly
DeansList SFTP job.

**Tech Stack:** dbt (BigQuery), Dagster (`build_bigquery_query_sftp_asset`),
single-PR cross-project workflow.

Spec:
`docs/superpowers/specs/2026-07-14-deanslist-family-contacts-extract-design.md`
Issue: [#4400](https://github.com/TEAMSchools/teamster/issues/4400)

## Global Constraints

- Single PR on branch `cbini/feat/claude-deanslist-family-contacts` (worktree
  `/workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts`).
- Output columns named exactly: `StudentID`, `ParentFirstName`,
  `ParentLastName`, `HomePhone`, `WorkPhone`, `CellPhone`, `Email`,
  `Relationship`, `Language` (always null).
- File must be named `contacts.txt` — `file_config` `stem: contacts`,
  `suffix: txt`.
- NJ regions only:
  `_dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')`.
- Currently enrolled only: `stg_powerschool__students.enroll_status = 0`.
- `contact_name` in the package model must NOT change — existing consumers
  depend on it.
- All git commands use
  `git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts`;
  all Read/Edit/Write target worktree paths.
- All dbt commands:
  `uv run dbt ... --project-dir <worktree>/src/dbt/<project> --profiles-dir /workspaces/teamster/.dbt`
  with `--state` as an ABSOLUTE path to the main repo's `target/prod`.
- SQL follows `src/dbt/CLAUDE.md` conventions (ST06 column order, no QUALIFY, no
  ORDER BY, trailing commas, 88-char lines). Trunk formats at commit.
- PII values from validation queries never leave local surfaces (no PR/issue
  bodies).

---

### Task 1: finalsite package — split contact names

**Files:**

- Modify:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql`
- Modify:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml`

**Interfaces:**

- Produces: columns `contact_first_name` (string), `contact_last_name` (string)
  on `int_finalsite__student_contacts` in every district project. Task 3's rpt
  model consumes them through the kipptaf union wrapper.

- [ ] **Step 1: Add the name columns to the model SQL**

Six edits to `int_finalsite__student_contacts.sql` (line refs are pre-edit):

1. `contact_1_typed` CTE (~line 45): after `cp.phone_1_number,` add:

```sql
            cp.first_name,
            cp.last_name,
```

2. `contact_1` CTE (~line 83): after `home_address,` add:

```sql
            first_name as contact_first_name,
            last_name as contact_last_name,
```

3. `emergency_long` CTE, all FOUR union branches (N = 1–4): in each branch,
   after `emrg_N_lives_with_yn as is_household_member,` add (substituting N):

```sql
            emrg_N_name_first_name as contact_first_name,
            emrg_N_name_last_name as contact_last_name,
```

4. `emergency` CTE (~line 246): after `contact_name,` add:

```sql
            contact_first_name,
            contact_last_name,
```

5. Final select, `contact_1` branch (~line 272): after `contact_name,` add:

```sql
    contact_first_name,
    contact_last_name,
```

6. Final select, `emergency` branch (~line 293): same two lines after
   `contact_name,`.

`contact_name` itself is untouched.

- [ ] **Step 2: Add the columns to the properties yml**

In `int_finalsite__student_contacts.yml`, after the `contact_name` column block,
add:

```yaml
- name: contact_first_name
  data_type: string
  description:
    Contact's first name — the related person's Finalsite `first_name` for
    `contact_1`, or `emrg_N_name_first_name` for an emergency slot.
  config:
    meta:
      contains_pii: true
- name: contact_last_name
  data_type: string
  description:
    Contact's last name — the related person's Finalsite `last_name` for
    `contact_1`, or `emrg_N_name_last_name` for an emergency slot.
  config:
    meta:
      contains_pii: true
```

- [ ] **Step 3: Install packages and build into the dev schema (one district)**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/kippnewark
uv run dbt build --select int_finalsite__student_contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/kippnewark \
  --profiles-dir /workspaces/teamster/.dbt \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kippnewark/target/prod
```

Expected: PASS (model + its uniqueness/not_null tests).

- [ ] **Step 4: Verify names populate and rows are unchanged (BigQuery MCP)**

```sql
select
    contact_slot,
    count(*) as n,
    countif(contact_first_name is null) as null_first,
    countif(contact_last_name is null) as null_last,
    countif(
        contact_slot = 'contact_1'
        and contact_name != concat(contact_first_name, ' ', contact_last_name)
    ) as name_mismatch,
from `teamster-332318`.zz_cbini_kippnewark_finalsite.int_finalsite__student_contacts
group by contact_slot
```

Expected: row counts per slot match prod
(`kippnewark_finalsite.int_finalsite__student_contacts` — run the same
`count(*) group by contact_slot` there); `null_first`/`null_last` near zero for
`contact_1`. `name_mismatch` is informational — `rel_name` may format
differently than first + last; do not block on it, but report the count.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts add \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts commit \
  -m "feat(finalsite): split contact first/last names in int_finalsite__student_contacts

Refs #4400

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: kipptaf NJ finalsite sources — staging schema branch

**Files:**

- Modify:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/kipptaf/models/finalsite/sources-kippnewark.yml`
- Modify: same-path `sources-kippcamden.yml`
- Modify: same-path `sources-kipppaterson.yml`

**Interfaces:**

- Produces: under `target=staging` (dbt Cloud CI), the three NJ finalsite
  sources resolve to `zz_stg_kipp<district>_finalsite`, which Task 5 seeds with
  the new columns.

- [ ] **Step 1: Add the staging branch to each source schema**

In each of the three files, replace the `schema:` expression (keep the district
name matching the file). Current form (Newark shown):

```yaml
schema:
  "{%- if target.name == 'dev' -%}zz_{{ env_var('GITHUB_USER', 'dev') }}_{%-
  endif -%}kippnewark_finalsite"
```

New form (mirrors `sources-kippmiami.yml`):

```yaml
schema:
  "{%- if target.name == 'dev' -%}zz_{{ env_var('GITHUB_USER', 'dev') }}_{%-
  elif target.name == 'staging' -%}zz_stg_{%- endif -%}kippnewark_finalsite"
```

Repeat for `kippcamden_finalsite` and `kipppaterson_finalsite`.

- [ ] **Step 2: Parse to verify**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/kipptaf
uv run dbt parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/kipptaf \
  --profiles-dir /workspaces/teamster/.dbt --target dev
```

Expected: parse succeeds, no YAML errors.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts add \
  src/dbt/kipptaf/models/finalsite/sources-kippnewark.yml \
  src/dbt/kipptaf/models/finalsite/sources-kippcamden.yml \
  src/dbt/kipptaf/models/finalsite/sources-kipppaterson.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts commit \
  -m "feat(kipptaf): staging schema branch for NJ finalsite sources

Refs #4400

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `rpt_deanslist__family_contacts` model

**Files:**

- Create:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql`
- Create:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml`

**Interfaces:**

- Consumes: `contact_first_name` / `contact_last_name` from Task 1 (via the
  kipptaf `int_finalsite__student_contacts` union wrapper).
- Produces: view `kipptaf_extracts.rpt_deanslist__family_contacts` with columns
  `StudentID` (int64), `ParentFirstName`, `ParentLastName`, `HomePhone`,
  `WorkPhone`, `CellPhone`, `Email`, `Relationship`, `Language` (all string).
  Task 4's extract asset queries it by name.

- [ ] **Step 1: Write the model SQL**

`rpt_deanslist__family_contacts.sql`:

```sql
with
    parent_contacts as (
        select
            sc.contact_first_name,
            sc.contact_last_name,
            sc.email,
            sc.phone_home,
            sc.phone_work,
            sc.phone_mobile,
            sc.relationship,
            sc._dbt_source_project,

            safe_cast(xw.powerschool_student_number as int64) as student_number,
        from {{ ref("int_finalsite__student_contacts") }} as sc
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as xw
            on sc.finalsite_enrollment_id = xw.finalsite_enrollment_id
            and sc._dbt_source_project = xw._dbt_source_project
        where
            sc.contact_slot = 'contact_1'
            and sc._dbt_source_project
            in ('kippnewark', 'kippcamden', 'kipppaterson')
            and xw.powerschool_student_number is not null
    ),

    enrolled_students as (
        select
            student_number,

            {{ extract_code_location("stg_powerschool__students") }}
            as _dbt_source_project,
        from {{ ref("stg_powerschool__students") }}
        where enroll_status = 0
    )

select
    pc.student_number as `StudentID`,
    pc.contact_first_name as `ParentFirstName`,
    pc.contact_last_name as `ParentLastName`,
    pc.phone_home as `HomePhone`,
    pc.phone_work as `WorkPhone`,
    pc.phone_mobile as `CellPhone`,
    pc.email as `Email`,
    pc.relationship as `Relationship`,

    cast(null as string) as `Language`,
from parent_contacts as pc
inner join
    enrolled_students as s
    on pc.student_number = s.student_number
    and pc._dbt_source_project = s._dbt_source_project
```

Notes for the implementer:

- `extract_code_location` (macro in `kipptaf/macros/utils.sql`) derives the
  district from `_dbt_source_relation` — `stg_powerschool__students` carries no
  `_dbt_source_project` of its own.
- The finalsite wrappers both materialize `_dbt_source_project`, so their join
  uses direct equality per `src/dbt/kipptaf/CLAUDE.md`.

- [ ] **Step 2: Write the properties yml**

`properties/rpt_deanslist__family_contacts.yml`:

```yaml
models:
  - name: rpt_deanslist__family_contacts
    description:
      DeansList nightly Family Contacts import (`contacts.txt`) for the NJ
      regions — one row per currently enrolled student carrying their single
      Finalsite parent contact (`contact_1` — the relationship flagged primary,
      falling back to financial). Emergency contacts are excluded. Column names
      match the DeansList import template headers exactly. Delivered by the
      Dagster asset `kipptaf/extracts/deanslist/contacts_txt`.
    columns:
      - name: StudentID
        data_type: int64
        description:
          PowerSchool student number, from the Finalsite contact's
          `powerschool_student_number` id attribute.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: ParentFirstName
        data_type: string
        description: Parent contact's first name.
        config:
          meta:
            contains_pii: true
      - name: ParentLastName
        data_type: string
        description: Parent contact's last name.
        config:
          meta:
            contains_pii: true
      - name: HomePhone
        data_type: string
        description: Parent contact's phone number typed `Home`, if any.
        config:
          meta:
            contains_pii: true
      - name: WorkPhone
        data_type: string
        description: Parent contact's phone number typed `Work`, if any.
        config:
          meta:
            contains_pii: true
      - name: CellPhone
        data_type: string
        description: Parent contact's phone number typed `Cell`, if any.
        config:
          meta:
            contains_pii: true
      - name: Email
        data_type: string
        description: Parent contact's email address.
        config:
          meta:
            contains_pii: true
      - name: Relationship
        data_type: string
        description:
          Relationship to the student (`parent`, `stepparent`, `guardian`,
          `grandparent`, etc.) — Finalsite `rel_type`.
      - name: Language
        data_type: string
        description:
          Always null — the header is required by the DeansList template, but
          Finalsite parent-language data is not maintained reliably enough to
          send.
```

- [ ] **Step 3: Build the district models into dev (all three NJ districts)**

The kipptaf wrapper reads district sources at
`zz_cbini_kipp<district>_finalsite` under `target=dev`. Newark was built in Task
1; build Camden and Paterson:

```bash
for d in kippcamden kipppaterson; do
  uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/$d
  uv run dbt build --select int_finalsite__student_contacts \
    --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/$d \
    --profiles-dir /workspaces/teamster/.dbt \
    --target dev --defer \
    --state /workspaces/teamster/src/dbt/$d/target/prod
done
```

Expected: PASS for both.

- [ ] **Step 4: Build the kipptaf wrapper + rpt into dev**

```bash
uv run dbt build --select int_finalsite__student_contacts rpt_deanslist__family_contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/kipptaf \
  --profiles-dir /workspaces/teamster/.dbt \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS — wrapper view rebuilds over the three dev district tables; rpt
view + `unique`/`not_null` tests on `StudentID` pass.
(`int_finalsite__contact_id_attributes` and `stg_powerschool__students` defer to
prod.)

- [ ] **Step 5: Validate the output (BigQuery MCP; values stay local)**

Coverage vs enrolled population:

```sql
with
    extract_rows as (
        select
            count(*) as n_rows,
            count(distinct StudentID) as n_students,
            countif(ParentFirstName is null) as null_first,
            countif(ParentLastName is null) as null_last,
            countif(Relationship is null) as null_rel,
            countif(
                Email is null and HomePhone is null
                and WorkPhone is null and CellPhone is null
            ) as unreachable,
        from `teamster-332318`.zz_cbini_kipptaf_extracts.rpt_deanslist__family_contacts
    ),

    enrolled as (
        select count(*) as n_enrolled,
        from `teamster-332318`.kipptaf_powerschool.stg_powerschool__students
        where
            enroll_status = 0
            and regexp_extract(_dbt_source_relation, r'(kipp\w+)_')
            in ('kippnewark', 'kippcamden', 'kipppaterson')
    )

select *, from extract_rows cross join enrolled
```

Expected: `n_rows = n_students` (unique already enforced); `n_rows / n_enrolled`
reported as coverage (students with no flagged parent contact or no SIS
crosswalk drop out — some gap is expected; flag to the user if coverage is below
~90%). If `null_first` + `null_last` + `null_rel` are all 0, additionally add
warn-severity `not_null` tests to `ParentFirstName`, `ParentLastName`, and
`Relationship` in the properties yml (project default severity is warn — a bare
`- not_null` suffices); if non-zero, leave them off and report the counts.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts add \
  src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql \
  src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts commit \
  -m "feat(kipptaf): rpt_deanslist__family_contacts extract view

Refs #4400

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Dagster extract asset (YAML only)

**Files:**

- Modify:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/teamster/code_locations/kipptaf/extracts/config/deanslist-annual.yaml`

**Interfaces:**

- Consumes: `kipptaf_extracts.rpt_deanslist__family_contacts` (Task 3). The
  factory auto-derives the Dagster dep
  `kipptaf/extracts/rpt_deanslist__family_contacts`.
- Produces: asset `kipptaf/extracts/deanslist/contacts_txt` on the existing
  `deanslist_annual_extract_asset_job` (nightly 1:25 AM) — uploads
  `contacts.txt` (CSV with header) to the DeansList SFTP root.

- [ ] **Step 1: Add the config entry**

Append after the `rpt_deanslist__star` entry (before the `# increased resources`
comment) in `deanslist-annual.yaml`:

```yaml
- query_config:
    type: schema
    value:
      table:
        name: rpt_deanslist__family_contacts
        schema: kipptaf_extracts
  file_config:
    stem: contacts
    suffix: txt
```

- [ ] **Step 2: Verify the asset builds and is named correctly**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts run python -c "
from teamster.code_locations.kipptaf.extracts.assets import assets

keys = {a.key.to_user_string() for a in assets}
assert 'kipptaf/extracts/deanslist/contacts_txt' in keys
print('asset ok:', len(keys), 'extract assets')
"
```

Expected: `asset ok: <N> extract assets`. (Full `dagster definitions validate`
fails in the codespace on unset dlt credentials — the submodule import is the
documented check.)

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts add \
  src/teamster/code_locations/kipptaf/extracts/config/deanslist-annual.yaml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts commit \
  -m "feat(kipptaf): contacts.txt DeansList extract asset

Refs #4400

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Staging seeding, lint, push, PR

**Files:** none (operational).

**Interfaces:**

- Consumes: all prior tasks' commits.

- [ ] **Step 1: Trunk-check every changed file**

From inside the worktree (cwd matters):

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts && \
/workspaces/teamster/.trunk/tools/trunk check --no-fix \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml \
  src/dbt/kipptaf/models/finalsite/sources-kippnewark.yml \
  src/dbt/kipptaf/models/finalsite/sources-kippcamden.yml \
  src/dbt/kipptaf/models/finalsite/sources-kipppaterson.yml \
  src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql \
  src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml \
  src/teamster/code_locations/kipptaf/extracts/config/deanslist-annual.yaml \
  </dev/null
```

Expected: no issues (sqlfluff/yamllint fire here, not at commit). Fix and amend
the relevant commit if anything surfaces.

- [ ] **Step 2: Seed staging schemas — REQUIRES USER AUTHORIZATION**

These recreate shared `zz_stg_*` tables. Ask the user before running; if
declined, hand the commands to the user.

Per NJ district (`kippnewark`, `kippcamden`, `kipppaterson`):

```bash
for d in kippnewark kippcamden kipppaterson; do
  uv run dbt clone \
    --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/$d \
    --profiles-dir /workspaces/teamster/.dbt \
    --target staging \
    --state /workspaces/teamster/src/dbt/$d/target/prod
  uv run dbt build --select int_finalsite__student_contacts \
    --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts/src/dbt/$d \
    --profiles-dir /workspaces/teamster/.dbt \
    --target staging
done
```

Notes:

- The broad clone seeds missing `zz_stg_<district>_*` relations from prod
  (existing relations are skipped without `--full-refresh`; missing prod
  relations log a silent skip — fine).
- The `dbt build --target staging` then rebuilds the MODIFIED
  `int_finalsite__student_contacts` from the cloned staging parents so
  `zz_stg_<district>_finalsite.int_finalsite__student_contacts` carries the new
  name columns. Verify afterwards via `INFORMATION_SCHEMA.COLUMNS` (expect
  `contact_first_name`, `contact_last_name` in all three districts).
- Do NOT proactively clone `zz_stg_kipptaf` — if CI later fails on a stale
  kipptaf staging relation, trigger the dbt Cloud `Clone - Staging (On-Demand)`
  job (`mcp__dbt__list_jobs` for the ID) and re-trigger CI with an empty
  commit + push.

- [ ] **Step 3: Push and open the PR**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-deanslist-family-contacts push
```

Create the PR with `mcp__github__create_pull_request` (base `main`, head
`cbini/feat/claude-deanslist-family-contacts`), title
`feat: DeansList family contacts extract (contacts.txt) for NJ regions`, body
following `.github/pull_request_template.md` with:

- Summary: what the extract is, single-PR cross-project rollout, staging seeding
  already performed, expected post-merge self-heal window while district prods
  rebuild.
- `Closes #4400`.
- Checked boxes only for items actually done (yml properties files ✓, staged
  staging schemas ✓, Dagster import check ✓; exposure N/A — DeansList extracts
  have no exposures, matching existing precedent).

- [ ] **Step 4: Monitor CI**

- dbt Cloud = commit status (`mcp__github__pull_request_read get_status`);
  Trunk/CodeQL/claude-review = check runs (`get_check_runs`). Check both.
- On dbt Cloud CI success, fetch warnings:
  `mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` —
  pre-existing warnings unchanged from `main` are fine.
- Review the `claude-review` comment; address valid findings, dismiss false
  positives with replies (verify its convention claims against
  `src/dbt/CLAUDE.md` first).
- Do not push fixes while a dbt Cloud run is in progress; bundle fixes into one
  push.

---

## Post-merge verification (after user merges)

Not part of the PR — run after merge lands:

1. `mcp__dagster__get_location_load_history` — confirm the new commit LOADED for
   kipptaf and the three NJ district locations.
2. Confirm district `int_finalsite__student_contacts` prods rematerialized
   (`mcp__dagster__get_asset_materializations`), then the kipptaf wrapper, then
   `kipptaf/extracts/rpt_deanslist__family_contacts`.
3. Confirm `kipptaf/extracts/deanslist/contacts_txt` materializes on the next
   1:25 AM run (or ask the user whether to `launch_run` it once) and that the
   run log shows `Saving file to .../contacts.txt`.
