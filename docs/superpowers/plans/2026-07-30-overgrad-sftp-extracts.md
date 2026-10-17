# Overgrad SFTP Extracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver four nightly CSV extracts (roster, GPA, SAT, AP) from the
warehouse to Overgrad's SIS Sync SFTP endpoint for Newark and Camden.

**Architecture:** Four network models in `kipptaf_extracts` carry a
`code_location` column and hold all diff logic against Overgrad. Eight thin
district passthroughs filter by `code_location` and project only the CSV
columns. Dagster's existing `build_bigquery_query_sftp_asset()` factory queries
each district model and uploads the file, following the
`rpt_powerschool__autocomm_students` pattern already in the repo.

**Tech Stack:** dbt (BigQuery), Dagster, `paramiko` via `SSHResource`, `uv` for
all Python execution.

**Spec:** `docs/superpowers/specs/2026-07-30-overgrad-sftp-extracts-design.md`

## Global Constraints

- **Worktree:** all work happens in
  `/workspaces/teamster/.worktrees/overgrad-sftp-extracts` on branch
  `CGibson17/feat/claude-overgrad-sftp-extracts`. Use `git -C <worktree>` on
  every git call and `--project-dir <worktree>/src/dbt/<project>` on every dbt
  call. Editing `/workspaces/teamster/<path>` instead silently dirties `main`.
- **Python:** always `uv run`. Never bare `python`, `dbt`, or `dagster`.
- **Contracts are enforced** on both `kipptaf` extracts
  (`src/dbt/kipptaf/dbt_project.yml:110-113`) and district extracts
  (`src/dbt/kippnewark/dbt_project.yml:35-38`). Every model column needs a
  `data_type` entry in its properties YAML or the build fails.
- **CSV headers are a vendor contract.** Column names in the district models
  become the CSV headers, and Overgrad's stored header mapping is keyed on them.
  Renaming a column silently breaks the sync. Do not rename columns to satisfy a
  linter.
- **Overgrad Student ID is the Salesforce contact id.** Every model filters
  `salesforce_id is not null`.
- **Every comparison against `int_overgrad__students` must join on both
  `external_student_id` and `_dbt_source_project`.** Omitting the source-project
  predicate silently suppresses Newark-to-Camden transfers.
- **Trunk:** do not run `trunk fmt`. Do run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree before pushing — sqlfluff and markdownlint fire only
  at pre-push and CI, not the pre-commit hook.
- **Overgrad accepted values are fixed strings** from the vendor spec. GPA type
  is `Unweighted` or `Weighted`. SAT tests are `New SAT`,
  `New SAT Evidence-Based Reading and Writing`, `New SAT Math`. AP tests are
  `AP Calculus AB`, `AP Calculus BC`, `AP Physics`, `AP US History`,
  `AP World History`. Do not invent variants.

---

## Task 1: `SSH_OVERGRAD` resource

Adds the SSH resource both districts need. Credentials themselves are user-owned
— this task wires the plumbing so the credential drop-in is the only manual
step.

**Files:**

- Modify: `src/teamster/core/resources.py` (add after `SSH_COUCHDROP`,
  ~line 116)
- Modify: `src/teamster/code_locations/kippnewark/definitions.py`
- Modify: `src/teamster/code_locations/kippcamden/definitions.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `SSH_OVERGRAD` importable from `teamster.core.resources`, and the
  resource key `ssh_overgrad` available in both district definitions. Task 10
  and Task 11 rely on `destination_config: {name: overgrad}` resolving to
  `ssh_overgrad`.

- [ ] **Step 1: Add the resource definition**

In `src/teamster/core/resources.py`, immediately after the `SSH_COUCHDROP`
block:

```python
SSH_OVERGRAD = SSHResource(
    remote_host=EnvVar("OVERGRAD_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("OVERGRAD_SFTP_USERNAME"),
    password=EnvVar("OVERGRAD_SFTP_PASSWORD"),
)
```

Note: Overgrad issues either a keyfile or a password (vendor spec, _SIS Sync
with SFTP_). This uses password auth. If the vendor issues a keyfile instead,
check `SSHResource` for the key parameter name before changing this — do not
guess.

- [ ] **Step 2: Verify the resource imports**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/overgrad-sftp-extracts \
  run python -c "from teamster.core.resources import SSH_OVERGRAD; print(SSH_OVERGRAD)"
```

Expected: prints an `SSHResource` repr. A `NameError` on `EnvVar` means the
import block at the top of `resources.py` is missing something — it should
already be there for the other SSH resources.

- [ ] **Step 3: Register in both district definitions**

In `src/teamster/code_locations/kippnewark/definitions.py`, add `SSH_OVERGRAD`
to the existing `from teamster.core.resources import (...)` block (keep
alphabetical order — `SSH_COUCHDROP` is at line 36), then add to the resources
dict alongside `"ssh_couchdrop": SSH_COUCHDROP` (line 105):

```python
        "ssh_overgrad": SSH_OVERGRAD,
```

Repeat identically in `src/teamster/code_locations/kippcamden/definitions.py`
(import at line 33, resources dict at line 92).

- [ ] **Step 4: Verify both locations still load**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/overgrad-sftp-extracts \
  run python -c "import ast,sys
for p in ['src/teamster/code_locations/kippnewark/definitions.py','src/teamster/code_locations/kippcamden/definitions.py']:
    ast.parse(open(p).read()); print('parsed', p)"
```

Expected: `parsed` for both. Full `dagster definitions validate` needs dbt
manifests and credentials that are absent in the Codespace — do not attempt it
here; Task 10 and 11 cover deploy-time validation.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/overgrad-sftp-extracts add \
  src/teamster/core/resources.py \
  src/teamster/code_locations/kippnewark/definitions.py \
  src/teamster/code_locations/kippcamden/definitions.py
git -C /workspaces/teamster/.worktrees/overgrad-sftp-extracts commit -m "feat(dagster): add SSH_OVERGRAD resource

Wires ssh_overgrad into kippnewark and kippcamden for the Overgrad SIS
Sync SFTP extracts.

Refs #4649"
```

**HANDOFF TO USER — do not attempt these:** creating the credential store item,
adding the three `OVERGRAD_SFTP_*` entries to each district's
`dagster-cloud.yaml` `container_config.env` block, and adding the item to
`.k8s/1password/items.yaml`. The pattern to follow is the `COUCHDROP_SFTP_*`
block at `src/teamster/code_locations/kippnewark/dagster-cloud.yaml:34-43`.
These require the vendor credentials, which arrive per the Aug 3-7 milestone.

---

## Task 2: `rpt_overgrad__students` network model

**Files:**

- Create: `src/dbt/kipptaf/models/extracts/overgrad/rpt_overgrad__students.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/overgrad/properties/rpt_overgrad__students.yml`

**Interfaces:**

- Consumes: `int_extracts__student_enrollments` (columns `_dbt_source_project`,
  `salesforce_id`, `student_email`, `student_first_name`, `student_last_name`,
  `school`, `graduation_year`, `has_fafsa`, `academic_year`, `rn_year`,
  `school_level`, `enroll_status`), `int_overgrad__students`
  (`external_student_id`, `_dbt_source_project`).
- Produces: table `kipptaf_extracts.rpt_overgrad__students` with columns
  `code_location` (string), `student_id` (string), `email` (string),
  `first_name` (string), `last_name` (string), `high_school` (string),
  `graduation_year` (int64), `fafsa_completed` (string). Task 3 selects all of
  these except `code_location`.

- [ ] **Step 1: Write the model**

Create `src/dbt/kipptaf/models/extracts/overgrad/rpt_overgrad__students.sql`:

```sql
with
    overgrad_existing as (
        select external_student_id, _dbt_source_project,
        from {{ ref("int_overgrad__students") }}
        where external_student_id is not null
    )

select
    e._dbt_source_project as code_location,
    e.salesforce_id as student_id,
    e.student_email as email,
    e.student_first_name as first_name,
    e.student_last_name as last_name,
    e.school as high_school,
    e.graduation_year,

    e.has_fafsa as fafsa_completed,
from {{ ref("int_extracts__student_enrollments") }} as e
left join
    overgrad_existing as o
    on e.salesforce_id = o.external_student_id
    and e._dbt_source_project = o._dbt_source_project
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.rn_year = 1
    and e.school_level = 'HS'
    and e.enroll_status = 0
    and e.salesforce_id is not null
    /* Drop this single predicate if Q12 confirms StudentSisFile supports
       upsert; the rest of the model is already upsert-shaped. */
    and o.external_student_id is null
```

The `left join` plus `o.external_student_id is null` is an anti-join written so
the filter is one removable line. Do not rewrite it as `not exists` or `not in`
— that couples the anti-join into the structure and defeats the Q12 hedge.

- [ ] **Step 2: Write the properties YAML**

Create
`src/dbt/kipptaf/models/extracts/overgrad/properties/rpt_overgrad__students.yml`:

```yaml
models:
  - name: rpt_overgrad__students
    description: >-
      Students to create or update in Overgrad, one row per student. Gated on
      `salesforce_id is not null` because Overgrad's Student ID is the
      Salesforce contact id — a student with no contact id cannot be linked.
      Anti-joined against students already present in Overgrad on both external
      id and source project; the source-project predicate keeps a
      Newark-to-Camden transfer from being treated as already rostered in
      Camden.
    config:
      meta:
        contains_pii: true
    columns:
      - name: code_location
        data_type: string
      - name: student_id
        data_type: string
      - name: email
        data_type: string
      - name: first_name
        data_type: string
      - name: last_name
        data_type: string
      - name: high_school
        data_type: string
      - name: graduation_year
        data_type: int64
      - name: fafsa_completed
        data_type: string
```

`contains_pii: true` is required — this model carries names, email, and student
ids, all FERPA direct identifiers.

- [ ] **Step 3: Build the model**

Run:

```bash
uv run dbt build --select rpt_overgrad__students \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

Expected: PASS. A contract error naming a column means the `data_type` in the
YAML disagrees with the SQL — fix the YAML to match the SQL, not the reverse,
unless the SQL type is genuinely wrong.

- [ ] **Step 4: Sanity-check the output**

Run this against the dev schema (substitute your dev schema prefix; the pattern
is `zz_<github_user>_kipptaf_extracts`):

```sql
select
    code_location,
    count(*) as students,
    count(distinct student_id) as distinct_ids,
    countif(email is null) as null_email,
    countif(high_school is null) as null_school,
from zz_<github_user>_kipptaf_extracts.rpt_overgrad__students
group by code_location
```

Expected: two `code_location` values (`kippnewark`, `kippcamden`);
`students = distinct_ids`; `null_email` and `null_school` both 0. Any null email
means a student would be rejected by Overgrad, since email is required to create
an account — investigate before proceeding rather than filtering it away.

- [ ] **Step 5: Add a duplicate-id data test**

Create
`src/dbt/kipptaf/tests/rpt_overgrad__students__student_id_unique_per_location.sql`:

```sql
select code_location, student_id,
from {{ ref("rpt_overgrad__students") }}
group by code_location, student_id
having count(*) > 1
```

Overgrad requires Student ID to be unique within a district. A duplicate here
means the file would be rejected or would silently overwrite one student with
another.

- [ ] **Step 6: Run the test**

Run:

```bash
uv run dbt test --select rpt_overgrad__students \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

Expected: PASS with 0 failing rows.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/overgrad-sftp-extracts && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/overgrad/rpt_overgrad__students.sql \
  src/dbt/kipptaf/models/extracts/overgrad/properties/rpt_overgrad__students.yml \
  src/dbt/kipptaf/tests/rpt_overgrad__students__student_id_unique_per_location.sql </dev/null
```

Expected: `No issues`. Then:

```bash
git -C /workspaces/teamster/.worktrees/overgrad-sftp-extracts add \
  src/dbt/kipptaf/models/extracts/overgrad/rpt_overgrad__students.sql \
  src/dbt/kipptaf/models/extracts/overgrad/properties/rpt_overgrad__students.yml \
  src/dbt/kipptaf/tests/rpt_overgrad__students__student_id_unique_per_location.sql
git -C /workspaces/teamster/.worktrees/overgrad-sftp-extracts commit -m "feat(kipptaf): add rpt_overgrad__students

Roster extract source, gated on a non-null Salesforce contact id and
anti-joined against students already in Overgrad on both external id and
source project.

Refs #4649"
```

---

## Task 3: `rpt_overgrad__students` district passthroughs

**Files:**

- Create:
  `src/dbt/kippnewark/models/extracts/overgrad/rpt_overgrad__students.sql`
- Create:
  `src/dbt/kippnewark/models/extracts/overgrad/properties/rpt_overgrad__students.yml`
- Create:
  `src/dbt/kippcamden/models/extracts/overgrad/rpt_overgrad__students.sql`
- Create:
  `src/dbt/kippcamden/models/extracts/overgrad/properties/rpt_overgrad__students.yml`
- Modify: `src/dbt/kippnewark/models/extracts/sources.yml`
- Modify: `src/dbt/kippcamden/models/extracts/sources.yml`

**Interfaces:**

- Consumes: `source("kipptaf_extracts", "rpt_overgrad__students")` from Task 2.
- Produces: `kippnewark_extracts.rpt_overgrad__students` and
  `kippcamden_extracts.rpt_overgrad__students`, each with exactly the seven CSV
  columns (`code_location` dropped). Task 10 and 11 query these by name.

- [ ] **Step 1: Add the source entry to both districts**

In `src/dbt/kippnewark/models/extracts/sources.yml`, append to the existing
`kipptaf_extracts` source's `tables:` list:

```yaml
- name: rpt_overgrad__students
  config:
    meta:
      dagster:
        group: extracts
        asset_key:
          - kipptaf
          - extracts
          - rpt_overgrad__students
```

Add the identical block to `src/dbt/kippcamden/models/extracts/sources.yml`. The
`asset_key` must be exactly `[kipptaf, extracts, rpt_overgrad__students]` —
asset keys do not include the dbt subdirectory, so no `overgrad` segment.

- [ ] **Step 2: Write the Newark passthrough**

Create `src/dbt/kippnewark/models/extracts/overgrad/rpt_overgrad__students.sql`:

```sql
select
    student_id,
    email,
    first_name,
    last_name,
    high_school,
    graduation_year,
    fafsa_completed,
from {{ source("kipptaf_extracts", "rpt_overgrad__students") }}
where code_location = '{{ project_name }}'
```

Column order here becomes CSV column order. Do not reorder it later.

- [ ] **Step 3: Write the Newark properties YAML**

Create
`src/dbt/kippnewark/models/extracts/overgrad/properties/rpt_overgrad__students.yml`:

```yaml
models:
  - name: rpt_overgrad__students
    description: >-
      Newark slice of the network Overgrad roster extract. Column names are the
      CSV headers Overgrad's stored header mapping is keyed on — renaming one
      breaks the SFTP sync silently.
    config:
      meta:
        contains_pii: true
    columns:
      - name: student_id
        data_type: string
      - name: email
        data_type: string
      - name: first_name
        data_type: string
      - name: last_name
        data_type: string
      - name: high_school
        data_type: string
      - name: graduation_year
        data_type: int64
      - name: fafsa_completed
        data_type: string
```

- [ ] **Step 4: Copy both files to Camden**

Create the same two files under `src/dbt/kippcamden/models/extracts/overgrad/`.
The SQL is byte-identical — `{{ project_name }}` resolves per project. In the
YAML, change only the word `Newark` to `Camden` in the description.

- [ ] **Step 5: Build both district models**

Run:

```bash
uv run dbt build --select rpt_overgrad__students \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kippnewark
uv run dbt build --select rpt_overgrad__students \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kippcamden
```

Expected: PASS for both. `Compilation Error ... source named 'kipptaf_extracts'`
means Step 1 was missed for that project.

- [ ] **Step 6: Verify the split is complete and disjoint**

Run:

```sql
select
    (select count(*) from zz_<github_user>_kippnewark_extracts.rpt_overgrad__students) as newark,
    (select count(*) from zz_<github_user>_kippcamden_extracts.rpt_overgrad__students) as camden,
    (select count(*) from zz_<github_user>_kipptaf_extracts.rpt_overgrad__students) as network
```

Expected: `newark + camden = network`. If they do not sum, a `code_location`
value exists that neither district claims — check for a third
`_dbt_source_project` value in the network model.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/overgrad-sftp-extracts && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kippnewark/models/extracts/overgrad/rpt_overgrad__students.sql \
  src/dbt/kippnewark/models/extracts/overgrad/properties/rpt_overgrad__students.yml \
  src/dbt/kippnewark/models/extracts/sources.yml \
  src/dbt/kippcamden/models/extracts/overgrad/rpt_overgrad__students.sql \
  src/dbt/kippcamden/models/extracts/overgrad/properties/rpt_overgrad__students.yml \
  src/dbt/kippcamden/models/extracts/sources.yml </dev/null
```

Then commit those six files with message:

```text
feat(dbt): add district Overgrad roster passthroughs

Newark and Camden slices of rpt_overgrad__students. Column order is the
CSV column order Overgrad's header mapping is keyed on.

Refs #4649
```

---

## Task 4: `rpt_overgrad__gpas` network model

> **GATED on stakeholder answers Q1-Q5.** Build this only after the GPA meeting.
> The spec's placeholder is `college_match_gpa` labeled `Unweighted`. If Q1
> selects a PowerSchool GPA, swap the source column. If Q3 asks for both types,
> the model becomes two `union all` branches. If Q4 answers anything other than
> "nightly whenever Salesforce changes", the diff logic changes shape and this
> task needs re-planning, not just re-coding.

**Files:**

- Create: `src/dbt/kipptaf/models/extracts/overgrad/rpt_overgrad__gpas.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/overgrad/properties/rpt_overgrad__gpas.yml`

**Interfaces:**

- Consumes: `int_extracts__student_enrollments` (`college_match_gpa` numeric,
  plus the same gate columns as Task 2), `int_overgrad__students`
  (`academics__unweighted_gpa`, `external_student_id`, `_dbt_source_project`).
- Produces: `kipptaf_extracts.rpt_overgrad__gpas` with `code_location` (string),
  `student_id` (string), `high_school` (string), `gpa_type` (string), `gpa`
  (numeric).

- [ ] **Step 1: Write the model**

Create `src/dbt/kipptaf/models/extracts/overgrad/rpt_overgrad__gpas.sql`:

```sql
with
    overgrad_gpa as (
        select
            external_student_id,
            _dbt_source_project,
            academics__unweighted_gpa,
        from {{ ref("int_overgrad__students") }}
        where external_student_id is not null
    )

select
    e._dbt_source_project as code_location,
    e.salesforce_id as student_id,
    e.school as high_school,

    'Unweighted' as gpa_type,

    e.college_match_gpa as gpa,
from {{ ref("int_extracts__student_enrollments") }} as e
left join
    overgrad_gpa as o
    on e.salesforce_id = o.external_student_id
    and e._dbt_source_project = o._dbt_source_project
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.rn_year = 1
    and e.school_level = 'HS'
    and e.enroll_status = 0
    and e.salesforce_id is not null
    and e.college_match_gpa is not null
    /* Send only when the Overgrad value is absent or stale. Overgrad replaces
       the GPA of the same type on every upload, so re-sending an unchanged
       value is wasted work, not a correctness problem. */
    and (
        o.academics__unweighted_gpa is null
        or o.academics__unweighted_gpa != e.college_match_gpa
    )
```

`!=` is null-safe here only because the `is null` branch is checked first. Do
not collapse the two conditions into `!=` alone — a null Overgrad GPA would then
never match and no first-time GPA would ever send.

- [ ] **Step 2: Write the properties YAML**

Create
`src/dbt/kipptaf/models/extracts/overgrad/properties/rpt_overgrad__gpas.yml`:

```yaml
models:
  - name: rpt_overgrad__gpas
    description: >-
      GPAs to send to Overgrad, one row per student per GPA type. Sent only when
      the Overgrad-side value is absent or differs, since Overgrad replaces the
      GPA of the same type on every upload. Typed `Unweighted` because
      Overgrad's match algorithm only runs off an unweighted GPA. Source column
      and type label are pending stakeholder confirmation (Q1-Q3).
    config:
      meta:
        contains_pii: true
    columns:
      - name: code_location
        data_type: string
      - name: student_id
        data_type: string
      - name: high_school
        data_type: string
      - name: gpa_type
        data_type: string
      - name: gpa
        data_type: numeric
```

- [ ] **Step 3: Build the model**

Run:

```bash
uv run dbt build --select rpt_overgrad__gpas \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

Expected: PASS.

- [ ] **Step 4: Verify the 4.0-scale assumption**

Overgrad requires a 4.0 scale and does not rescale. Run:

```sql
select
    min(gpa) as min_gpa,
    max(gpa) as max_gpa,
    countif(gpa > 4.0) as above_four,
    countif(gpa < 0) as negative,
from zz_<github_user>_kipptaf_extracts.rpt_overgrad__gpas
```

Expected: `max_gpa <= 4.0`, `above_four = 0`, `negative = 0`. **If `above_four`
is non-zero, stop and report it** — the source is on a different scale and Q2
was answered wrong. Do not add a rescaling expression without stakeholder
sign-off; silently dividing GPAs is worse than a failed build.

- [ ] **Step 5: Add a scale guard data test**

Create
`src/dbt/kipptaf/tests/rpt_overgrad__gpas__gpa_within_four_point_scale.sql`:

```sql
select student_id, gpa,
from {{ ref("rpt_overgrad__gpas") }}
where gpa > 4.0 or gpa < 0
```

- [ ] **Step 6: Run the test**

Run:

```bash
uv run dbt test --select rpt_overgrad__gpas \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

Expected: PASS with 0 rows.

- [ ] **Step 7: Lint and commit**

Lint the three files with the `trunk check --force --no-fix` command shape from
Task 2 Step 7, then commit:

```text
feat(kipptaf): add rpt_overgrad__gpas

GPA extract source. Sends only when the Overgrad-side unweighted GPA is
absent or differs. Typed Unweighted because Overgrad's match algorithm
requires it. Guards the 4.0-scale requirement with a data test.

Refs #4649
```

---

## Task 5: `rpt_overgrad__gpas` district passthroughs

**Files:**

- Create: `src/dbt/kippnewark/models/extracts/overgrad/rpt_overgrad__gpas.sql`
- Create:
  `src/dbt/kippnewark/models/extracts/overgrad/properties/rpt_overgrad__gpas.yml`
- Create: `src/dbt/kippcamden/models/extracts/overgrad/rpt_overgrad__gpas.sql`
- Create:
  `src/dbt/kippcamden/models/extracts/overgrad/properties/rpt_overgrad__gpas.yml`
- Modify: `src/dbt/kippnewark/models/extracts/sources.yml`
- Modify: `src/dbt/kippcamden/models/extracts/sources.yml`

**Interfaces:**

- Consumes: `source("kipptaf_extracts", "rpt_overgrad__gpas")` from Task 4.
- Produces: `<district>_extracts.rpt_overgrad__gpas` with four CSV columns.

- [ ] **Step 1: Add the source entry to both districts**

Append to the `kipptaf_extracts` `tables:` list in both
`src/dbt/kippnewark/models/extracts/sources.yml` and
`src/dbt/kippcamden/models/extracts/sources.yml`:

```yaml
- name: rpt_overgrad__gpas
  config:
    meta:
      dagster:
        group: extracts
        asset_key:
          - kipptaf
          - extracts
          - rpt_overgrad__gpas
```

- [ ] **Step 2: Write the passthrough SQL for both districts**

Create the identical file at
`src/dbt/kippnewark/models/extracts/overgrad/rpt_overgrad__gpas.sql` and
`src/dbt/kippcamden/models/extracts/overgrad/rpt_overgrad__gpas.sql`:

```sql
select
    student_id,
    high_school,
    gpa_type,
    gpa,
from {{ source("kipptaf_extracts", "rpt_overgrad__gpas") }}
where code_location = '{{ project_name }}'
```

- [ ] **Step 3: Write the properties YAML for both districts**

Create at
`src/dbt/kippnewark/models/extracts/overgrad/properties/rpt_overgrad__gpas.yml`
(and the Camden equivalent, changing only `Newark` to `Camden`):

```yaml
models:
  - name: rpt_overgrad__gpas
    description: >-
      Newark slice of the network Overgrad GPA extract. Column names are the CSV
      headers Overgrad's stored header mapping is keyed on.
    config:
      meta:
        contains_pii: true
    columns:
      - name: student_id
        data_type: string
      - name: high_school
        data_type: string
      - name: gpa_type
        data_type: string
      - name: gpa
        data_type: numeric
```

- [ ] **Step 4: Build both**

Run:

```bash
uv run dbt build --select rpt_overgrad__gpas \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kippnewark
uv run dbt build --select rpt_overgrad__gpas \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kippcamden
```

Expected: PASS for both.

- [ ] **Step 5: Verify the split sums**

Run:

```sql
select
    (select count(*) from zz_<github_user>_kippnewark_extracts.rpt_overgrad__gpas) as newark,
    (select count(*) from zz_<github_user>_kippcamden_extracts.rpt_overgrad__gpas) as camden,
    (select count(*) from zz_<github_user>_kipptaf_extracts.rpt_overgrad__gpas) as network
```

Expected: `newark + camden = network`.

- [ ] **Step 6: Lint and commit**

Commit the six files:

```text
feat(dbt): add district Overgrad GPA passthroughs

Refs #4649
```

---

## Task 6: `rpt_overgrad__test_scores` network model

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/overgrad/rpt_overgrad__test_scores.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/overgrad/properties/rpt_overgrad__test_scores.yml`

**Interfaces:**

- Consumes: `int_assessments__college_assessment` (`student_number` int64,
  `test_date` date, `scope` string, `score_type` string, `scale_score` numeric),
  `int_extracts__student_enrollments` (`student_number`, `salesforce_id`,
  `school`, `_dbt_source_project`, `academic_year`, `rn_year`).
- Produces: `kipptaf_extracts.rpt_overgrad__test_scores` with `code_location`
  (string), `student_id` (string), `high_school` (string), `test_date` (string),
  `test` (string), `score` (numeric).

`test_date` is a **string**, not a date — Overgrad requires `mm/dd/yyyy`, and
formatting it in SQL keeps the CSV writer from emitting an ISO date.

- [ ] **Step 1: Write the model**

Create `src/dbt/kipptaf/models/extracts/overgrad/rpt_overgrad__test_scores.sql`:

```sql
with
    enrollments as (
        select
            _dbt_source_project,
            student_number,
            salesforce_id,
            school,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
            and salesforce_id is not null
    ),

    sat_scores as (
        select
            student_number,
            test_date,
            scale_score,

            case
                score_type
                when 'sat_total_score'
                then 'New SAT'
                when 'sat_ebrw'
                then 'New SAT Evidence-Based Reading and Writing'
                when 'sat_math'
                then 'New SAT Math'
            end as overgrad_test,
        from {{ ref("int_assessments__college_assessment") }}
        where
            scope = 'SAT'
            and test_date is not null
            and scale_score is not null
            and score_type in ('sat_total_score', 'sat_ebrw', 'sat_math')
    )

select
    e._dbt_source_project as code_location,
    e.salesforce_id as student_id,
    e.school as high_school,

    format_date('%m/%d/%Y', s.test_date) as test_date,

    s.overgrad_test as `test`,

    s.scale_score as score,
from sat_scores as s
inner join enrollments as e on s.student_number = e.student_number
```

`score_type in (...)` is the allowlist that excludes the legacy
`sat_reading_test_score` and `sat_math_test_score` types. It is deliberately
redundant with the `case` — the `case` produces the label, the `where`
guarantees no row survives with a null label. Do not remove either.

`test` is backticked because it is a BigQuery reserved-ish identifier in some
contexts and the CSV header must be exactly `test`.

- [ ] **Step 2: Write the properties YAML**

Create
`src/dbt/kipptaf/models/extracts/overgrad/properties/rpt_overgrad__test_scores.yml`:

```yaml
models:
  - name: rpt_overgrad__test_scores
    description: >-
      SAT scores to send to Overgrad, one row per student per test per date.
      Sourced from Salesforce via int_assessments__college_assessment. Full
      resend every run — there is no Overgrad test-score API to diff against, so
      idempotency relies on the vendor overwriting matching test-and-date
      records. See the follow-up issue on moving to a sent-row ledger.
    config:
      meta:
        contains_pii: true
    columns:
      - name: code_location
        data_type: string
      - name: student_id
        data_type: string
      - name: high_school
        data_type: string
      - name: test_date
        data_type: string
      - name: test
        data_type: string
      - name: score
        data_type: numeric
```

- [ ] **Step 3: Build the model**

Run:

```bash
uv run dbt build --select rpt_overgrad__test_scores \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

Expected: PASS.

- [ ] **Step 4: Verify no PSAT leaked and no label is null**

Run:

```sql
select `test`, count(*) as rows_out, min(test_date) as earliest, max(test_date) as latest,
from zz_<github_user>_kipptaf_extracts.rpt_overgrad__test_scores
group by `test`
order by `test`
```

Expected: exactly three `test` values, all from the accepted list, none null,
none containing `PSAT`. The spec documents why `scope = 'SAT'` cannot admit a
PSAT row (`stg_collegeboard__psat` sets `test_type` from a closed `case`
yielding only `PSAT NMSQT`, `PSAT 8/9`, `PSAT10`); this query confirms it in
data.

- [ ] **Step 5: Add a same-test-same-day data test**

Overgrad rejects two scores for the same test on the same day. Create
`src/dbt/kipptaf/tests/rpt_overgrad__test_scores__no_same_test_same_day.sql`:

```sql
select code_location, student_id, `test`, test_date,
from {{ ref("rpt_overgrad__test_scores") }}
group by code_location, student_id, `test`, test_date
having count(*) > 1
```

- [ ] **Step 6: Run the test**

Run:

```bash
uv run dbt test --select rpt_overgrad__test_scores \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

Expected: PASS with 0 rows. **If this fails, do not add a dedupe to make it
pass** — a genuine duplicate means the same student has two SAT records for one
test on one date upstream, which is a data question for the assessments owner,
not something to paper over in an extract.

- [ ] **Step 7: Lint and commit**

```text
feat(kipptaf): add rpt_overgrad__test_scores

SAT extract source. Maps the three current score types to Overgrad's
accepted test names and formats the date as mm/dd/yyyy. Guards the
vendor's same-test-same-day rejection with a data test.

Refs #4649
```

---

## Task 7: `rpt_overgrad__test_scores` district passthroughs

**Files:**

- Create:
  `src/dbt/kippnewark/models/extracts/overgrad/rpt_overgrad__test_scores.sql`
- Create:
  `src/dbt/kippnewark/models/extracts/overgrad/properties/rpt_overgrad__test_scores.yml`
- Create:
  `src/dbt/kippcamden/models/extracts/overgrad/rpt_overgrad__test_scores.sql`
- Create:
  `src/dbt/kippcamden/models/extracts/overgrad/properties/rpt_overgrad__test_scores.yml`
- Modify: `src/dbt/kippnewark/models/extracts/sources.yml`
- Modify: `src/dbt/kippcamden/models/extracts/sources.yml`

**Interfaces:**

- Consumes: `source("kipptaf_extracts", "rpt_overgrad__test_scores")` from
  Task 6.
- Produces: `<district>_extracts.rpt_overgrad__test_scores` with five CSV
  columns.

- [ ] **Step 1: Add the source entry to both districts**

```yaml
- name: rpt_overgrad__test_scores
  config:
    meta:
      dagster:
        group: extracts
        asset_key:
          - kipptaf
          - extracts
          - rpt_overgrad__test_scores
```

- [ ] **Step 2: Write the passthrough SQL for both districts**

```sql
select
    student_id,
    high_school,
    test_date,
    `test`,
    score,
from {{ source("kipptaf_extracts", "rpt_overgrad__test_scores") }}
where code_location = '{{ project_name }}'
```

- [ ] **Step 3: Write the properties YAML for both districts**

```yaml
models:
  - name: rpt_overgrad__test_scores
    description: >-
      Newark slice of the network Overgrad SAT extract. Column names are the CSV
      headers Overgrad's stored header mapping is keyed on.
    config:
      meta:
        contains_pii: true
    columns:
      - name: student_id
        data_type: string
      - name: high_school
        data_type: string
      - name: test_date
        data_type: string
      - name: test
        data_type: string
      - name: score
        data_type: numeric
```

- [ ] **Step 4: Build both**

```bash
uv run dbt build --select rpt_overgrad__test_scores \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kippnewark
uv run dbt build --select rpt_overgrad__test_scores \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kippcamden
```

Expected: PASS for both.

- [ ] **Step 5: Verify the split sums**

Run:

```sql
select
    (select count(*) from zz_<github_user>_kippnewark_extracts.rpt_overgrad__test_scores) as newark,
    (select count(*) from zz_<github_user>_kippcamden_extracts.rpt_overgrad__test_scores) as camden,
    (select count(*) from zz_<github_user>_kipptaf_extracts.rpt_overgrad__test_scores) as network
```

Expected: `newark + camden = network`.

- [ ] **Step 6: Lint and commit**

```text
feat(dbt): add district Overgrad SAT passthroughs

Refs #4649
```

---

## Task 8: `rpt_overgrad__ap_scores` network model

The most failure-prone model in this plan. Read the AP subsection of the spec
before starting.

**Files:**

- Create: `src/dbt/kipptaf/models/extracts/overgrad/rpt_overgrad__ap_scores.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/overgrad/properties/rpt_overgrad__ap_scores.yml`

**Interfaces:**

- Consumes: `int_assessments__ap_assessments` (`academic_year`,
  `powerschool_student_number`, `test_subject`, `exam_score`, `ap_course_name`,
  `data_source`), `int_extracts__student_enrollments` (`student_number`,
  `salesforce_id`, `school`, `_dbt_source_project`).
- Produces: `kipptaf_extracts.rpt_overgrad__ap_scores` with `code_location`
  (string), `student_id` (string), `high_school` (string), `test_date` (string),
  `test` (string), `score` (int64).

- [ ] **Step 1: Discover the actual subject vocabulary before writing any
      mapping**

The two union branches inside `int_assessments__ap_assessments` use different
subject vocabularies: the Salesforce branch sets `test_subject` from
`int_kippadb__standardized_test_unpivot`, the College Board branch from
`exam_code_description`. Run:

```sql
select
    data_source,
    ap_course_name,
    test_subject,
    count(*) as rows_out,
from {{ ref("int_assessments__ap_assessments") }}
where
    lower(coalesce(ap_course_name, test_subject)) like '%calculus%'
    or lower(coalesce(ap_course_name, test_subject)) like '%physics%'
    or lower(coalesce(ap_course_name, test_subject)) like '%history%'
group by data_source, ap_course_name, test_subject
order by data_source, ap_course_name, test_subject
```

Run it with `dbt show` so `ref()` resolves:

```bash
uv run dbt show --inline "$(cat <<'SQL'
select data_source, ap_course_name, test_subject, count(*) as rows_out,
from {{ ref("int_assessments__ap_assessments") }}
group by data_source, ap_course_name, test_subject
order by data_source, ap_course_name, test_subject
SQL
)" --limit 200 \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

**Record the output before continuing.** The `case` in Step 3 must match the
values that actually exist, in both vocabularies. Do not write the mapping from
memory of College Board naming.

- [ ] **Step 2: Confirm the `academic_year` convention on the Salesforce
      branch**

This is the spec's one open data question. For the College Board branch,
`academic_year = admin_year - 1`, so an exam sat in May 2024 has
`academic_year = 2023`. The Salesforce branch's `academic_year` comes from
`int_kippadb__standardized_test_unpivot` and may not follow that convention.
Run:

```bash
uv run dbt show --inline "$(cat <<'SQL'
select data_source, academic_year, count(*) as rows_out,
from {{ ref("int_assessments__ap_assessments") }}
group by data_source, academic_year
order by data_source, academic_year
SQL
)" --limit 200 \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

The College Board branch is filtered to `academic_year >= 2018` and the
Salesforce branch to `< 2018`, so the two ranges must not overlap. If they do,
or if the Salesforce years look shifted by one relative to the CB years, **stop
and report it** — the synthesized date would be a year off for pre-2018 scores.
Do not guess a correction.

- [ ] **Step 3: Verify the join key type**

`int_assessments__ap_assessments` has no properties YAML, so
`powerschool_student_number` has no declared type, while
`int_extracts__student_enrollments.student_number` is `int64`. Run:

```bash
uv run dbt show --inline "$(cat <<'SQL'
select powerschool_student_number,
from {{ ref("int_assessments__ap_assessments") }}
limit 5
SQL
)" --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

If the values render quoted, the column is a string and the join in Step 4 needs
`safe_cast(a.powerschool_student_number as int64)`. Use `safe_cast`, not `cast`
— a non-numeric id should drop out rather than fail the build.

- [ ] **Step 4: Write the model**

Create `src/dbt/kipptaf/models/extracts/overgrad/rpt_overgrad__ap_scores.sql`.
Adjust the `case` branches to the values recorded in Step 1, and add the
`safe_cast` from Step 3 if needed:

```sql
with
    enrollments as (
        select
            _dbt_source_project,
            student_number,
            salesforce_id,
            school,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
            and salesforce_id is not null
    ),

    mapped as (
        select
            a.powerschool_student_number,
            a.exam_score,

            date(a.academic_year + 1, 5, 15) as test_date,

            case
                when
                    lower(coalesce(a.ap_course_name, a.test_subject))
                    like '%calculus ab%'
                then 'AP Calculus AB'
                when
                    lower(coalesce(a.ap_course_name, a.test_subject))
                    like '%calculus bc%'
                then 'AP Calculus BC'
                when lower(coalesce(a.ap_course_name, a.test_subject)) like '%physics%'
                then 'AP Physics'
                when
                    lower(coalesce(a.ap_course_name, a.test_subject))
                    like '%united states history%'
                    or lower(coalesce(a.ap_course_name, a.test_subject))
                    like '%us history%'
                then 'AP US History'
                when
                    lower(coalesce(a.ap_course_name, a.test_subject))
                    like '%world history%'
                then 'AP World History'
            end as overgrad_test,
        from {{ ref("int_assessments__ap_assessments") }} as a
        where a.exam_score is not null and a.academic_year is not null
    ),

    deduplicated as (
        select
            powerschool_student_number,
            test_date,
            overgrad_test,

            max(exam_score) as exam_score,
        from mapped
        where overgrad_test is not null
        group by powerschool_student_number, test_date, overgrad_test
    )

select
    e._dbt_source_project as code_location,
    e.salesforce_id as student_id,
    e.school as high_school,

    format_date('%m/%d/%Y', d.test_date) as test_date,

    d.overgrad_test as `test`,

    d.exam_score as score,
from deduplicated as d
inner join enrollments as e on d.powerschool_student_number = e.student_number
```

Three things not to change:

- The `group by` with `max(exam_score)` is the Physics collapse fix. Four
  College Board Physics exams map to one `AP Physics`, and Overgrad rejects two
  scores for the same test on the same day. Do not replace it with
  `int_assessments__ap_assessments.rn_highest` — that column partitions by
  `(powerschool_student_number, ap_course_name)` across all years and would drop
  a legitimate retake in a later year.
- `date(a.academic_year + 1, 5, 15)` synthesizes the May exam date. AP exams
  have no date in the source at all.
- `overgrad_test is not null` filters unsupported AP subjects. Overgrad accepts
  only five.

- [ ] **Step 5: Write the properties YAML**

Create
`src/dbt/kipptaf/models/extracts/overgrad/properties/rpt_overgrad__ap_scores.yml`:

```yaml
models:
  - name: rpt_overgrad__ap_scores
    description: >-
      AP scores to send to Overgrad, limited to the five AP subjects Overgrad
      accepts. Sourced from int_assessments__ap_assessments rather than
      int_collegeboard__ap_unpivot because the wrapper discards College Board
      crosswalk misses instead of collapsing NULL-keyed rows. Test date is
      synthesized as May 15 of academic_year + 1 since AP scores carry no exam
      date. Deduplicated to the highest score per student per Overgrad test per
      date, which collapses College Board's four Physics exams into one AP
      Physics record.
    config:
      meta:
        contains_pii: true
    columns:
      - name: code_location
        data_type: string
      - name: student_id
        data_type: string
      - name: high_school
        data_type: string
      - name: test_date
        data_type: string
      - name: test
        data_type: string
      - name: score
        data_type: int64
```

If Step 4's `exam_score` turns out to be `numeric` rather than `int64`, set the
`data_type` to match the SQL — AP scores are 1-5 integers, but the upstream
column type governs.

- [ ] **Step 6: Build the model**

Run:

```bash
uv run dbt build --select rpt_overgrad__ap_scores \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

Expected: PASS. Note the AP chain depends on
`stg_google_sheets__collegeboard__ap_id_crosswalk`, a Drive-backed source. `dbt`
runs on ADC which has Drive scope, so the build works — but the BigQuery MCP
cannot read Drive-backed tables, so run validation queries against the
materialized model, not the raw source.

- [ ] **Step 7: Add an unmapped-subject data test**

The `case` uses `like` patterns, so a new or renamed subject could fall through
to null and vanish. Create
`src/dbt/kipptaf/tests/rpt_overgrad__ap_scores__mapped_subjects_are_accepted.sql`:

```sql
select `test`, count(*) as rows_out,
from {{ ref("rpt_overgrad__ap_scores") }}
where
    `test` not in (
        'AP Calculus AB',
        'AP Calculus BC',
        'AP Physics',
        'AP US History',
        'AP World History'
    )
group by `test`
```

- [ ] **Step 8: Add a same-test-same-day data test**

Create
`src/dbt/kipptaf/tests/rpt_overgrad__ap_scores__no_same_test_same_day.sql`:

```sql
select code_location, student_id, `test`, test_date,
from {{ ref("rpt_overgrad__ap_scores") }}
group by code_location, student_id, `test`, test_date
having count(*) > 1
```

This is the test that proves the Physics collapse fix works. It must pass.

- [ ] **Step 9: Run both tests**

Run:

```bash
uv run dbt test --select rpt_overgrad__ap_scores \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

Expected: PASS with 0 rows for both.

- [ ] **Step 10: Quantify what the crosswalk is dropping**

The College Board ID crosswalk gap is a known recurring failure with its own
test (`int_collegeboard__ap_unpivot__crosswalk_resolves`). Run it and record the
count:

```bash
uv run dbt test --select int_collegeboard__ap_unpivot__crosswalk_resolves \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

A non-zero failure count is students whose AP scores will not reach Overgrad.
**Report the number rather than fixing it here** — clearing crosswalk gaps is an
ops task against the Google Sheet, tracked separately, and must happen before
the September validation window.

- [ ] **Step 11: Lint and commit**

```text
feat(kipptaf): add rpt_overgrad__ap_scores

AP extract source, limited to Overgrad's five accepted subjects and
sourced from int_assessments__ap_assessments so College Board crosswalk
misses are discarded rather than collapsed. Synthesizes the May exam
date and dedupes to the highest score per student, test, and date, which
resolves the four-Physics-exams-to-one-AP-Physics collision.

Refs #4649
```

---

## Task 9: `rpt_overgrad__ap_scores` district passthroughs

**Files:**

- Create:
  `src/dbt/kippnewark/models/extracts/overgrad/rpt_overgrad__ap_scores.sql`
- Create:
  `src/dbt/kippnewark/models/extracts/overgrad/properties/rpt_overgrad__ap_scores.yml`
- Create:
  `src/dbt/kippcamden/models/extracts/overgrad/rpt_overgrad__ap_scores.sql`
- Create:
  `src/dbt/kippcamden/models/extracts/overgrad/properties/rpt_overgrad__ap_scores.yml`
- Modify: `src/dbt/kippnewark/models/extracts/sources.yml`
- Modify: `src/dbt/kippcamden/models/extracts/sources.yml`

**Interfaces:**

- Consumes: `source("kipptaf_extracts", "rpt_overgrad__ap_scores")` from Task 8.
- Produces: `<district>_extracts.rpt_overgrad__ap_scores` with five CSV columns,
  identical in shape to the SAT passthrough.

- [ ] **Step 1: Add the source entry to both districts**

```yaml
- name: rpt_overgrad__ap_scores
  config:
    meta:
      dagster:
        group: extracts
        asset_key:
          - kipptaf
          - extracts
          - rpt_overgrad__ap_scores
```

- [ ] **Step 2: Write the passthrough SQL for both districts**

```sql
select
    student_id,
    high_school,
    test_date,
    `test`,
    score,
from {{ source("kipptaf_extracts", "rpt_overgrad__ap_scores") }}
where code_location = '{{ project_name }}'
```

- [ ] **Step 3: Write the properties YAML for both districts**

Create at
`src/dbt/kippnewark/models/extracts/overgrad/properties/rpt_overgrad__ap_scores.yml`
(and the Camden equivalent, changing only `Newark` to `Camden`):

```yaml
models:
  - name: rpt_overgrad__ap_scores
    description: >-
      Newark slice of the network Overgrad AP extract. Column names are the CSV
      headers Overgrad's stored header mapping is keyed on.
    config:
      meta:
        contains_pii: true
    columns:
      - name: student_id
        data_type: string
      - name: high_school
        data_type: string
      - name: test_date
        data_type: string
      - name: test
        data_type: string
      - name: score
        data_type: int64
```

If Task 8 Step 5 set `score` to `numeric` because the upstream `exam_score`
column is numeric, use `numeric` here too. The two must agree or the contract
fails.

- [ ] **Step 4: Build both**

```bash
uv run dbt build --select rpt_overgrad__ap_scores \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kippnewark
uv run dbt build --select rpt_overgrad__ap_scores \
  --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kippcamden
```

Expected: PASS for both.

- [ ] **Step 5: Verify the split sums**

Run:

```sql
select
    (select count(*) from zz_<github_user>_kippnewark_extracts.rpt_overgrad__ap_scores) as newark,
    (select count(*) from zz_<github_user>_kippcamden_extracts.rpt_overgrad__ap_scores) as camden,
    (select count(*) from zz_<github_user>_kipptaf_extracts.rpt_overgrad__ap_scores) as network
```

Expected: `newark + camden = network`. The network model already inner-joins the
current-year enrollment set, so alumni AP scores are excluded upstream and the
district counts sum exactly.

Separately worth recording, though not a failure: compare the network row count
to the total AP rows available. The gap is AP scores belonging to students who
are no longer enrolled, which Overgrad has no use for. It is only alarming if
the network count is near zero.

```bash
uv run dbt show --inline "$(cat <<'SQL'
select count(*) as all_ap_rows,
from {{ ref("int_assessments__ap_assessments") }}
SQL
)" --project-dir /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/dbt/kipptaf
```

- [ ] **Step 6: Lint and commit**

```text
feat(dbt): add district Overgrad AP passthroughs

Refs #4649
```

---

## Task 10: Dagster wiring for `kippnewark`

**Files:**

- Create: `src/teamster/code_locations/kippnewark/extracts/config/overgrad.yaml`
- Modify: `src/teamster/code_locations/kippnewark/extracts/assets.py`
- Modify: `src/teamster/code_locations/kippnewark/extracts/jobs.py`
- Modify: `src/teamster/code_locations/kippnewark/extracts/schedules.py`

**Interfaces:**

- Consumes: `ssh_overgrad` from Task 1, and the four
  `kippnewark_extracts.rpt_overgrad__*` tables from Tasks 3, 5, 7, 9.
- Produces: four assets keyed `[kippnewark, extracts, overgrad, <stem>_csv]`,
  one job `kippnewark__extracts__overgrad__asset_job`, one schedule at
  `0 4 * * *`.

- [ ] **Step 1: Write the config**

Create `src/teamster/code_locations/kippnewark/extracts/config/overgrad.yaml`:

```yaml
assets:
  - query_config:
      type: schema
      value:
        table:
          schema: kippnewark_extracts
          name: rpt_overgrad__students
    file_config:
      stem: overgrad_students
      suffix: csv
    destination_config:
      name: overgrad
      path: uploads/StudentSisFile
  - query_config:
      type: schema
      value:
        table:
          schema: kippnewark_extracts
          name: rpt_overgrad__gpas
    file_config:
      stem: overgrad_gpas
      suffix: csv
    destination_config:
      name: overgrad
      path: uploads/GpaSisFile
  - query_config:
      type: schema
      value:
        table:
          schema: kippnewark_extracts
          name: rpt_overgrad__test_scores
    file_config:
      stem: overgrad_test_scores
      suffix: csv
    destination_config:
      name: overgrad
      path: uploads/NationalTestScoreSisFile
  - query_config:
      type: schema
      value:
        table:
          schema: kippnewark_extracts
          name: rpt_overgrad__ap_scores
    file_config:
      stem: overgrad_ap_scores
      suffix: csv
    destination_config:
      name: overgrad
      path: uploads/NationalTestScoreSisFile
```

Three notes:

- `type: schema` is required, not `text` or `file`. Only the schema form gets
  the `zz_dagster_` prefix redirect on branch deployments
  (`libraries/extracts/assets.py` `construct_query`), so a branch deploy would
  otherwise read production tables.
- The GPA and test-score directory names are **placeholders pending vendor
  question Q18**. The vendor spec names only `uploads/StudentSisFile/`
  explicitly. Do not send to Overgrad until Q18 confirms these two paths.
- AP and SAT both target the test-score directory because they are the same
  Overgrad import type. Two files landing in one directory is fine — Overgrad
  processes first come, first served.

- [ ] **Step 2: Add the assets**

In `src/teamster/code_locations/kippnewark/extracts/assets.py`, add after the
existing `powerschool_extract_assets` block:

```python
overgrad_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/overgrad.yaml"])["assets"]
]
```

Then add `*overgrad_extract_assets,` to the `assets` list at the bottom.

- [ ] **Step 3: Add the job**

In `src/teamster/code_locations/kippnewark/extracts/jobs.py`, add
`overgrad_extract_assets` to the existing import from `...extracts.assets`,
then:

```python
overgrad_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__overgrad__asset_job",
    selection=overgrad_extract_assets,
)
```

- [ ] **Step 4: Add the schedule**

In `src/teamster/code_locations/kippnewark/extracts/schedules.py`, add
`overgrad_extract_asset_job` to the existing import, then:

```python
overgrad_extract_assets_schedule = ScheduleDefinition(
    job=overgrad_extract_asset_job,
    cron_schedule="0 4 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)
```

Add `overgrad_extract_assets_schedule,` to the `schedules` list.

`0 4 * * *` is deliberate and differs from the `0 3 * * *` used by every other
extract in this file. Overgrad's stated preferred transfer window is 4am to 6am
ET and it processes files on receipt; 3am would arrive before the window opens.

- [ ] **Step 5: Verify the module parses and the assets build**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/overgrad-sftp-extracts \
  run python -c "
from dagster import config_from_files
c = config_from_files(['src/teamster/code_locations/kippnewark/extracts/config/overgrad.yaml'])
assert len(c['assets']) == 4, c
for a in c['assets']:
    print(a['file_config']['stem'], '->', a['destination_config']['path'])
"
```

Expected: four lines, each stem paired with its upload directory. This exercises
the same `config_from_files` call the asset factory uses, so a YAML typo
surfaces here rather than at deploy.

- [ ] **Step 6: Commit**

```text
feat(dagster): add Overgrad SFTP extracts for kippnewark

Four CSV extracts on a 4am schedule, inside Overgrad's stated 4-6am ET
processing window rather than the 3am used by other extracts here.

GPA and test-score upload directories are provisional pending vendor
confirmation of the exact subdirectory names.

Refs #4649
```

---

## Task 11: Dagster wiring for `kippcamden`

Identical to Task 10 with `kippcamden` substituted throughout.

**Files:**

- Create: `src/teamster/code_locations/kippcamden/extracts/config/overgrad.yaml`
- Modify: `src/teamster/code_locations/kippcamden/extracts/assets.py`
- Modify: `src/teamster/code_locations/kippcamden/extracts/jobs.py`
- Modify: `src/teamster/code_locations/kippcamden/extracts/schedules.py`

**Interfaces:**

- Consumes: `ssh_overgrad` from Task 1, and the four
  `kippcamden_extracts.rpt_overgrad__*` tables from Tasks 3, 5, 7, 9.
- Produces: four assets keyed `[kippcamden, extracts, overgrad, <stem>_csv]`,
  one job `kippcamden__extracts__overgrad__asset_job`, one schedule at
  `0 4 * * *`.

- [ ] **Step 1: Write the config**

Create `src/teamster/code_locations/kippcamden/extracts/config/overgrad.yaml`:

```yaml
assets:
  - query_config:
      type: schema
      value:
        table:
          schema: kippcamden_extracts
          name: rpt_overgrad__students
    file_config:
      stem: overgrad_students
      suffix: csv
    destination_config:
      name: overgrad
      path: uploads/StudentSisFile
  - query_config:
      type: schema
      value:
        table:
          schema: kippcamden_extracts
          name: rpt_overgrad__gpas
    file_config:
      stem: overgrad_gpas
      suffix: csv
    destination_config:
      name: overgrad
      path: uploads/GpaSisFile
  - query_config:
      type: schema
      value:
        table:
          schema: kippcamden_extracts
          name: rpt_overgrad__test_scores
    file_config:
      stem: overgrad_test_scores
      suffix: csv
    destination_config:
      name: overgrad
      path: uploads/NationalTestScoreSisFile
  - query_config:
      type: schema
      value:
        table:
          schema: kippcamden_extracts
          name: rpt_overgrad__ap_scores
    file_config:
      stem: overgrad_ap_scores
      suffix: csv
    destination_config:
      name: overgrad
      path: uploads/NationalTestScoreSisFile
```

The `file_config.stem` values match Newark's on purpose — the two districts are
separate Overgrad accounts on separate SFTP servers, so identical filenames do
not collide. The GPA and test-score `path` values remain provisional pending
Q18.

- [ ] **Step 2: Add the assets**

In `src/teamster/code_locations/kippcamden/extracts/assets.py`, add after the
existing `powerschool_extract_assets` block:

```python
overgrad_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/overgrad.yaml"])["assets"]
]
```

Then add `*overgrad_extract_assets,` to the `assets` list at the bottom.
`CODE_LOCATION` and `LOCAL_TIMEZONE` come from the existing
`from teamster.code_locations.kippcamden import ...` line already at the top of
that file.

- [ ] **Step 3: Add the job**

In `src/teamster/code_locations/kippcamden/extracts/jobs.py`, add
`overgrad_extract_assets` to the existing import from `...extracts.assets`,
then:

```python
overgrad_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__overgrad__asset_job",
    selection=overgrad_extract_assets,
)
```

- [ ] **Step 4: Add the schedule**

In `src/teamster/code_locations/kippcamden/extracts/schedules.py`, add
`overgrad_extract_asset_job` to the existing import, then:

```python
overgrad_extract_assets_schedule = ScheduleDefinition(
    job=overgrad_extract_asset_job,
    cron_schedule="0 4 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)
```

Add `overgrad_extract_assets_schedule,` to the `schedules` list. As with Newark,
`0 4 * * *` is deliberate — Overgrad's processing window is 4-6am ET.

- [ ] **Step 5: Verify the config parses**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/overgrad-sftp-extracts \
  run python -c "
from dagster import config_from_files
c = config_from_files(['src/teamster/code_locations/kippcamden/extracts/config/overgrad.yaml'])
assert len(c['assets']) == 4, c
for a in c['assets']:
    print(a['query_config']['value']['table']['schema'], a['file_config']['stem'])
"
```

Expected: four lines, each naming `kippcamden_extracts`.

- [ ] **Step 6: Verify no schema crossed over**

Run:

```bash
grep -c 'kippnewark' \
  /workspaces/teamster/.worktrees/overgrad-sftp-extracts/src/teamster/code_locations/kippcamden/extracts/config/overgrad.yaml
```

Expected: `0`. A copy-paste that leaves `kippnewark_extracts` in Camden's config
would send Newark students to Camden's Overgrad account — the exact
cross-contamination the source-project predicate elsewhere is designed to
prevent.

- [ ] **Step 7: Commit**

```text
feat(dagster): add Overgrad SFTP extracts for kippcamden

Refs #4649
```

---

## Task 12: Dry run to `couchdrop`, then validate

Produces the real CSVs without any vendor-visible action. `SSH_COUCHDROP` is
already wired into both district definitions, so this needs no new resource.

**Files:**

- Modify (temporarily):
  `src/teamster/code_locations/kippnewark/extracts/config/overgrad.yaml`

**Interfaces:**

- Consumes: everything from Tasks 1-11.
- Produces: four inspected CSV files and a go or no-go decision on the live
  send. No committed code changes — the config edit is reverted before commit.

- [ ] **Step 1: Point Newark's config at couchdrop**

In `src/teamster/code_locations/kippnewark/extracts/config/overgrad.yaml`,
change all four `destination_config` blocks to:

```yaml
destination_config:
  name: couchdrop
  path: teamster-kippnewark/couchdrop/overgrad-dryrun
```

Do not commit this. It is reverted in Step 5.

- [ ] **Step 2: Run the job**

Materialize the four Newark Overgrad extract assets. Ask the user to launch
`kippnewark__extracts__overgrad__asset_job` from the Dagster UI, or launch the
assets individually with `mcp__dagster__launch_run` using asset keys
`kippnewark/extracts/overgrad/<stem>_csv`. Preview with `confirm=False` first.

Expected: four successful materializations. A `KeyError` on `ssh_couchdrop`
means Task 1 registered `ssh_overgrad` but this dry run needs `ssh_couchdrop`,
which is already present — recheck the resource key spelling in the config.

- [ ] **Step 3: Inspect every CSV against the vendor spec**

Download the four files and check each one:

- Header row present, and header names exactly match the district model column
  names.
- `test_date` renders as `mm/dd/yyyy`, not `yyyy-mm-dd`. This is the single most
  likely formatting failure.
- `gpa_type` is exactly `Unweighted`.
- AP `test` values are only the five accepted strings.
- No row has an empty `student_id`, `email`, or `high_school`.
- Row counts match the warehouse counts from Tasks 3, 5, 7, and 9.

- [ ] **Step 4: Confirm no PII leaves the local environment**

These files contain names, emails, and student ids. Keep them in
`.claude/scratch/` or the terminal. Do not paste rows into the GitHub issue, the
PR, Asana, or any comment. Report findings as counts and column names, or with
redacted labels like `Student A`.

- [ ] **Step 5: Revert the config**

```bash
git -C /workspaces/teamster/.worktrees/overgrad-sftp-extracts checkout -- \
  src/teamster/code_locations/kippnewark/extracts/config/overgrad.yaml
git -C /workspaces/teamster/.worktrees/overgrad-sftp-extracts status --short
```

Expected: clean tree for that file. Verify before moving on — leaving the
dry-run destination committed would silently route production Overgrad data to
couchdrop.

- [ ] **Step 6: Record the outcome**

Add a comment to issue #4649 with the row counts per file, the date-format check
result, and any discrepancies. Counts and column names only — no student rows.

---

## Task 13: Documentation and follow-ups

**Files:**

- Modify: `docs/reference/adding-an-integration.md` (only if the Overgrad SFTP
  egress introduces a pattern not already documented there — read it first and
  skip if it does not)
- Modify: `src/dbt/kipptaf/CLAUDE.md`
- Modify: `src/teamster/code_locations/kippnewark/CLAUDE.md`
- Modify: `src/teamster/code_locations/kippcamden/CLAUDE.md`

**Interfaces:**

- Consumes: the finished pipeline.
- Produces: documentation and tracking issues. No code.

- [ ] **Step 1: Regenerate the automations catalog — or do not**

Two new schedules were added, so `docs/reference/automations.md` is stale. **Do
not run `uv run scripts/gen-automations-doc.py` in the Codespace** — it silently
skips code locations that fail to import, and several will, which would delete
them from the catalog. Note in the PR that the catalog needs regenerating in a
full environment, and leave the file alone.

- [ ] **Step 2: Add the Overgrad egress note to the dbt CLAUDE.md**

In `src/dbt/kipptaf/CLAUDE.md`, add one line under the extracts guidance:

```markdown
- **Overgrad extract column names are a vendor contract.** Overgrad's stored
  SFTP header mapping is keyed on the CSV headers, which are the district model
  column names. Renaming a column in `rpt_overgrad__*` breaks the sync silently
  — no error, just no data.
```

Apply the CLAUDE.md necessity test before adding anything else: name the
specific decision a reader would make differently. If you cannot, do not add the
line.

- [ ] **Step 3: Add the schedule note to both district CLAUDE.mds**

In `src/teamster/code_locations/kippnewark/CLAUDE.md` and the `kippcamden`
equivalent:

```markdown
- **Overgrad extracts run at 4am, not 3am.** Overgrad's SFTP processing window
  is 4-6am ET and it processes files on receipt; a 3am delivery arrives before
  the window opens.
```

- [ ] **Step 4: Open the follow-up issues**

**Ask the user before opening these** — do not create issues unprompted.

- Test-score idempotency: replace the full resend with a ledger of sent rows if
  Overgrad rejects duplicate submissions. Reference the vendor doc's internal
  contradiction between the overwrite claim and the same-test-same-day
  prohibition.
- Welcome emails: SFTP-created accounts get none. Process owner needed. This is
  the item most likely to make a working pipeline look broken to students.
- ACT scores: already available in `int_assessments__college_assessment` and
  accepted by Overgrad. Low marginal cost, deferred from this build.
- The wrong `meta.source_model` on
  `int_extracts__student_enrollments.graduation_year` (claims
  `stg_powerschool__studentcorefields`, actual SQL is `adb.graduation_year`).
  Pre-existing repo doc bug found during this design.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/overgrad-sftp-extracts && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/CLAUDE.md \
  src/teamster/code_locations/kippnewark/CLAUDE.md \
  src/teamster/code_locations/kippcamden/CLAUDE.md </dev/null
```

Then commit:

```text
docs: note Overgrad extract header contract and 4am schedule

Refs #4649
```

---

## Open items this plan cannot close

- **Q1-Q5 (GPA)** gate Task 4. Task 5 depends on Task 4.
- **Q12 (upsert)** does not block anything — Task 2 is built upsert-shaped so
  the answer removes one filter line — but a create-only answer means re-testing
  the roster file.
- **Q18 (upload directories)** blocks the live send in Task 12's successor. The
  GPA and test-score paths in Tasks 10 and 11 are provisional.
- **Vendor credentials** block Task 1's handoff steps and everything downstream
  of the live send.
- **The Salesforce `academic_year` convention** for pre-2018 AP scores is a data
  check inside Task 8 Step 2. If it does not match the College Board convention,
  Task 8 needs re-planning before the AP file can be trusted.
- **College Board crosswalk gaps** are quantified in Task 8 Step 10 but cleared
  by Ops against the Google Sheet, not by this plan.
