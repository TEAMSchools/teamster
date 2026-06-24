# Finalsite → Focus SFTP transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the five `rpt_focus__*` models to Focus as a coordinated daily
SFTP drop of CSVs, with each model trimmed to exactly the Focus import contract.

**Architecture:** Reuse the existing `build_bigquery_query_sftp_asset` factory.
Five config-driven extract assets in the `kippmiami` code location read the
`kippmiami_extracts.rpt_focus__*` pass-through tables and push uppercase-headed
CSVs to a Focus SFTP destination via a new `SSH_FOCUS` resource, on a daily
(initially STOPPED) schedule. The `rpt_focus__*` models are first trimmed to
drop the columns Focus does not import.

**Tech Stack:** Python 3.13, Dagster, dbt (BigQuery), `uv`.

## Global Constraints

- **Worktree:** all work is in
  `.worktrees/cbini-feat-claude-focus-sftp-transport` on branch
  `cbini/feat/claude-focus-sftp-transport`. Treat that as the repo root (`cwd`)
  for every command below; Read/Edit/Write must target paths under it.
- **dbt in a worktree:** worktrees have no `dbt_packages/`. Once, before any dbt
  build, run `uv run dbt deps --project-dir src/dbt/kipptaf` and
  `uv run dbt deps --project-dir src/dbt/kippmiami`. Pass `--defer` with an
  **absolute** `--state` pointing at the MAIN repo's prod manifest:
  `/workspaces/teamster/src/dbt/<project>/target/prod`.
- **No `--target prod`** dbt runs (classifier-blocked). Local builds use the
  default/dev target with `--defer`.
- **Python:** always `uv run`; never bare `python`/`dbt`/`dagster`.
- **SQL style** (`.trunk/config/.sqlfluff`): BigQuery dialect, trailing comma
  required on the last `SELECT` column, single quotes, 88-char lines. The
  `rpt_focus__*` models carry `-- trunk-ignore(sqlfluff/ST06)` on line 1 to keep
  Focus column order — preserve it.
- **dbt contracts:** every `rpt_focus__*` model is contract-enforced; the
  `properties` yml `columns:` list must match the model's output columns by name
  and type, or the build fails.
- **dbt unit-test yaml:** `given`/`expect` scalars are UNQUOTED except
  leading-zero strings; do not add quotes when editing expects.
- **Trunk:** do not run `trunk fmt`/`check` manually for code; the pre-commit
  hook formats. For any `.md` you add, run
  `/workspaces/teamster/.trunk/tools/trunk check --force <file>` from inside the
  worktree before pushing.
- **Drop-column safety (pre-verified):** `tide_access_code`,
  `fl_days_absent_not_disc`, and `contact7_callout` appear only in
  `extracts/focus/` (the `fl_days_absent_not_disc` hit in `stg_focus__*` is the
  unrelated inbound Focus source). `mail_zipcode` and `relationship` are
  consumed only by the kippmiami wrappers trimmed in the same task.
- **#4205 overlap:** #4205 also edits `rpt_focus__demographics`,
  `rpt_focus__contacts`, and `rpt_focus__student_enrollment` (repointing the
  `STDT_ID` stub). If that branch is open, whichever merges second rebases to
  avoid a conflict. Before starting,
  `git fetch origin main && git merge origin/main`.
- **Commit messages:** conventional commits; end the body with
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: `SSH_FOCUS` resource

**Files:**

- Modify: `src/teamster/core/resources.py` (after the `SSH_COUCHDROP` block,
  ~line 111)
- Modify: `src/teamster/code_locations/kippmiami/definitions.py` (imports ~line
  24-39; resources dict ~line 73-89)

**Interfaces:**

- Produces: `SSH_FOCUS` (an `SSHResource`) importable from
  `teamster.core.resources`, wired into the kippmiami `Definitions.resources`
  under key `"ssh_focus"`. The Focus extract assets (Task 7) require the
  `ssh_focus` resource key at runtime.

- [ ] **Step 1: Add the resource in `core/resources.py`**

Insert immediately after the `SSH_COUCHDROP = SSHResource(...)` block (it ends
at the line `)` on ~line 111):

```python
SSH_FOCUS = SSHResource(
    remote_host=EnvVar("FOCUS_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("FOCUS_SFTP_USERNAME"),
    password=EnvVar("FOCUS_SFTP_PASSWORD"),
)
```

- [ ] **Step 2: Import it in `kippmiami/definitions.py`**

In the `from teamster.core.resources import (...)` block, add `SSH_FOCUS` to the
alphabetical list (before `SSH_COUCHDROP`):

```python
    SSH_FOCUS,
    SSH_COUCHDROP,
    SSH_IREADY,
    SSH_RENLEARN,
```

- [ ] **Step 3: Wire it into the resources dict**

In the `resources={...}` dict, add the `ssh_focus` entry (keep keys ordered):

```python
        "ssh_couchdrop": SSH_COUCHDROP,
        "ssh_focus": SSH_FOCUS,
        "ssh_iready": SSH_IREADY,
```

- [ ] **Step 4: Verify the module imports**

Run: `uv run python -c "import teamster.code_locations.kippmiami.definitions"`
Expected: exits 0, no traceback. (`SSH_FOCUS` referencing undefined env vars is
fine — `EnvVar` is lazy and only resolved at run time.)

- [ ] **Step 5: Commit**

```bash
git add src/teamster/core/resources.py src/teamster/code_locations/kippmiami/definitions.py
git commit -m "feat(dagster): add SSH_FOCUS resource for Focus SFTP transport"
```

---

### Task 2: Trim `rpt_focus__demographics` (drop `tide_access_code`)

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__demographics.sql:78`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__demographics.yml`
  (contract col ~line 200; unit-test expects ~lines 312, 357, 402)
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/rpt_focus__demographics.sql:44`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__demographics.yml`
  (the `tide_access_code` contract entry)

**Interfaces:**

- Produces: `rpt_focus__demographics` now outputs exactly the 42 Focus
  `DEMOGRAPHICS_LAYOUT` columns (Task 7's `header_replacements` map relies on
  this set).

- [ ] **Step 1: Drop the column from the kipptaf SQL**

Delete line 78 of
`src/dbt/kipptaf/models/extracts/focus/rpt_focus__demographics.sql`:

```sql
    cast(null as string) as tide_access_code,
```

The new last column is `cast(null as string) as lcp_cont_stdt,` (line 77) — it
keeps its trailing comma before `from`.

- [ ] **Step 2: Drop the contract column + unit-test expects in the kipptaf
      yml**

In
`src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__demographics.yml`:

- Delete the entire `- name: tide_access_code` block from `columns:` (~line 200)
  — its `name`, `data_type`, and `description` lines.
- Delete the `tide_access_code: null,` line from each of the three `expect` rows
  in `unit_tests` (~lines 312, 357, 402).

- [ ] **Step 3: Drop the column from the kippmiami wrapper SQL**

Delete line 44 of
`src/dbt/kippmiami/models/extracts/focus/rpt_focus__demographics.sql`:

```sql
    tide_access_code,
```

- [ ] **Step 4: Drop the contract column in the kippmiami wrapper yml**

In
`src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__demographics.yml`,
delete the `tide_access_code` entry:

```yaml
- name: tide_access_code
  data_type: string
```

- [ ] **Step 5: Build + unit-test the kipptaf model**

Run:
`uv run dbt build --select rpt_focus__demographics --project-dir src/dbt/kipptaf --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
Expected: PASS — model builds (contract satisfied with 42 columns) and
`test_demographics_shape` passes.

- [ ] **Step 6: Build the kippmiami wrapper**

Run:
`uv run dbt build --select rpt_focus__demographics --project-dir src/dbt/kippmiami --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/focus/rpt_focus__demographics.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__demographics.yml \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__demographics.sql \
  src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__demographics.yml
git commit -m "refactor(dbt): drop tide_access_code from rpt_focus__demographics (#4207)"
```

---

### Task 3: Trim `rpt_focus__student_enrollment` (drop `fl_days_absent_not_disc`)

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/focus/rpt_focus__student_enrollment.sql:51`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__student_enrollment.yml`
  (contract col ~line 158; unit-test expects ~lines 250, 281, 357)
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql:30`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__student_enrollment.yml`

**Interfaces:**

- Produces: `rpt_focus__student_enrollment` outputs exactly the 28 Focus
  `STUDENT_ENROLLMENT_LAYOUT` columns.

- [ ] **Step 1: Drop the column from the kipptaf SQL**

Delete line 51 of `.../kipptaf/.../rpt_focus__student_enrollment.sql`:

```sql
    cast(null as int64) as fl_days_absent_not_disc,
```

New last column: `cast(null as int64) as fl_days_absent,` (line 50).

- [ ] **Step 2: Drop the contract column + unit-test expects in the kipptaf
      yml**

In `.../kipptaf/.../properties/rpt_focus__student_enrollment.yml`:

- Delete the `- name: fl_days_absent_not_disc` contract block (~line 158).
- Delete `fl_days_absent_not_disc: null,` from each of the three `expect` rows
  (~lines 250, 281, 357) across `test_student_enrollment_shape` and
  `test_student_enrollment_transfer_out`.

- [ ] **Step 3: Drop the column from the kippmiami wrapper SQL**

Delete line 30 of `.../kippmiami/.../rpt_focus__student_enrollment.sql`:

```sql
    fl_days_absent_not_disc,
```

- [ ] **Step 4: Drop the contract column in the kippmiami wrapper yml**

Delete the `fl_days_absent_not_disc` entry from
`.../kippmiami/.../properties/rpt_focus__student_enrollment.yml`:

```yaml
- name: fl_days_absent_not_disc
  data_type: int64
```

- [ ] **Step 5: Build + unit-test the kipptaf model**

Run:
`uv run dbt build --select rpt_focus__student_enrollment --project-dir src/dbt/kipptaf --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
Expected: PASS — both unit tests pass, contract satisfied with 28 columns.

- [ ] **Step 6: Build the kippmiami wrapper**

Run:
`uv run dbt build --select rpt_focus__student_enrollment --project-dir src/dbt/kippmiami --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/focus/rpt_focus__student_enrollment.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__student_enrollment.yml \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__student_enrollment.sql \
  src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__student_enrollment.yml
git commit -m "refactor(dbt): drop fl_days_absent_not_disc from rpt_focus__student_enrollment (#4207)"
```

---

### Task 4: Trim `rpt_focus__addresses` (drop `mail_zipcode`)

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql:19`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml`
  (contract col ~line 64; unit-test expect ~line 105)
- Modify: `src/dbt/kippmiami/models/extracts/focus/rpt_focus__addresses.sql:14`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__addresses.yml:28-29`

**Interfaces:**

- Produces: `rpt_focus__addresses` outputs exactly the 12 Focus `ADDRESS_LAYOUT`
  columns.

- [ ] **Step 1: Drop the column from the kipptaf SQL**

Delete line 19 of `.../kipptaf/.../rpt_focus__addresses.sql`:

```sql
    cast(null as string) as mail_zipcode,
```

New last column: `cast(null as string) as mail_state,` (line 18).

- [ ] **Step 2: Drop the contract column + unit-test expect in the kipptaf yml**

In `.../kipptaf/.../properties/rpt_focus__addresses.yml`:

- Delete the `- name: mail_zipcode` contract block (~line 64).
- Delete `mail_zipcode: null,` from the `test_addresses_shape` expect row (~line
  105).

- [ ] **Step 3: Drop the column from the kippmiami wrapper SQL**

Delete line 14 of `.../kippmiami/.../rpt_focus__addresses.sql`:

```sql
    mail_zipcode,
```

- [ ] **Step 4: Drop the contract column in the kippmiami wrapper yml**

Delete lines 28-29 of `.../kippmiami/.../properties/rpt_focus__addresses.yml`:

```yaml
- name: mail_zipcode
  data_type: string
```

- [ ] **Step 5: Build + unit-test the kipptaf model**

Run:
`uv run dbt build --select rpt_focus__addresses --project-dir src/dbt/kipptaf --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
Expected: PASS.

- [ ] **Step 6: Build the kippmiami wrapper**

Run:
`uv run dbt build --select rpt_focus__addresses --project-dir src/dbt/kippmiami --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__addresses.sql \
  src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__addresses.yml
git commit -m "refactor(dbt): drop mail_zipcode from rpt_focus__addresses (#4207)"
```

---

### Task 5: Trim `rpt_focus__contacts` (drop `contact7_callout`)

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql:66`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`
  (description ~line 11; contract col ~lines 252-256; unit-test expects ~lines
  379, 432)
- Modify: `src/dbt/kippmiami/models/extracts/focus/rpt_focus__contacts.sql`
  (last column line, `contact7_callout,`)
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__contacts.yml`

**Interfaces:**

- Produces: `rpt_focus__contacts` outputs exactly the 50 Focus `CONTACTS_LAYOUT`
  columns.

> Note: `contact7_callout` is dropped per the parsed Focus layout (50 fields;
> contacts 1–6 have a callout, contact 7 does not). Per the spec this asymmetry
> is flagged for a Focus sanity-check; proceed with the drop and raise it if the
> sanity-check later contradicts.

- [ ] **Step 1: Drop the column from the kipptaf SQL**

Delete line 66 of `.../kipptaf/.../rpt_focus__contacts.sql`:

```sql
    cast(null as string) as contact7_callout,
```

New last column: `cast(null as string) as contact7_unlisted,` (line 65).

- [ ] **Step 2: Update the kipptaf yml — description, contract, unit-test
      expects**

In `.../kipptaf/.../properties/rpt_focus__contacts.yml`:

- In the model `description` (~line 11), change "Produces 51 columns in" to
  "Produces 50 columns in".
- Delete the `- name: contact7_callout` contract block (~lines 252-256).
- Delete `contact7_callout: null,` from both `expect` rows in
  `test_contacts_two_guardians` (~lines 379, 432).

- [ ] **Step 3: Drop the column from the kippmiami wrapper SQL**

In `.../kippmiami/.../rpt_focus__contacts.sql`, delete the last column line:

```sql
    contact7_callout,
```

New last column: `contact7_unlisted,`.

- [ ] **Step 4: Drop the contract column in the kippmiami wrapper yml**

Delete the `contact7_callout` entry from
`.../kippmiami/.../properties/rpt_focus__contacts.yml`:

```yaml
- name: contact7_callout
  data_type: string
```

- [ ] **Step 5: Build + unit-test the kipptaf model**

Run:
`uv run dbt build --select rpt_focus__contacts --project-dir src/dbt/kipptaf --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
Expected: PASS — `test_contacts_two_guardians` passes with 50-column expect
rows.

- [ ] **Step 6: Build the kippmiami wrapper**

Run:
`uv run dbt build --select rpt_focus__contacts --project-dir src/dbt/kippmiami --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__contacts.sql \
  src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__contacts.yml
git commit -m "refactor(dbt): drop contact7_callout from rpt_focus__contacts (#4207)"
```

---

### Task 6: Trim `rpt_focus__linked_students` (drop `relationship`)

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/focus/rpt_focus__linked_students.sql:10`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__linked_students.yml`
  (contract col ~line 37)
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/rpt_focus__linked_students.sql:1`
- Modify:
  `src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__linked_students.yml`

**Interfaces:**

- Produces: `rpt_focus__linked_students` outputs exactly the 2 Focus
  `LINKED_STUDENTS` columns.

> Note: the model is dormant (`where ... and false`, returns no rows) and its
> unit test `test_linked_students_dormant_until_stdt_id` expects zero rows — so
> no `expect`-row edit is needed, only the SQL and contract.

- [ ] **Step 1: Drop the column from the kipptaf SQL**

Delete line 10 of `.../kipptaf/.../rpt_focus__linked_students.sql`:

```sql
    'sibling' as relationship,
```

New last column: `cast(null as string) as secondary_student_id,` (line 8).

- [ ] **Step 2: Drop the contract column in the kipptaf yml**

In `.../kipptaf/.../properties/rpt_focus__linked_students.yml`, delete the
`- name: relationship` contract block (~lines 37-40, includes its description).
Confirm no `expect` row references `relationship`
(`grep -n "relationship" <file>` should show only the model-level description
and the input ref).

- [ ] **Step 3: Drop the column from the kippmiami wrapper SQL**

Edit line 1 of `.../kippmiami/.../rpt_focus__linked_students.sql`:

```sql
select primary_student_id, secondary_student_id,
```

- [ ] **Step 4: Drop the contract column in the kippmiami wrapper yml**

Delete the `relationship` entry from
`.../kippmiami/.../properties/rpt_focus__linked_students.yml`:

```yaml
- name: relationship
  data_type: string
```

- [ ] **Step 5: Build + unit-test the kipptaf model**

Run:
`uv run dbt build --select rpt_focus__linked_students --project-dir src/dbt/kipptaf --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
Expected: PASS — dormant unit test passes, contract satisfied with 2 columns.

- [ ] **Step 6: Build the kippmiami wrapper**

Run:
`uv run dbt build --select rpt_focus__linked_students --project-dir src/dbt/kippmiami --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/focus/rpt_focus__linked_students.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__linked_students.yml \
  src/dbt/kippmiami/models/extracts/focus/rpt_focus__linked_students.sql \
  src/dbt/kippmiami/models/extracts/focus/properties/rpt_focus__linked_students.yml
git commit -m "refactor(dbt): drop relationship from rpt_focus__linked_students (#4207)"
```

---

### Task 7: Focus SFTP extract assets

**Files:**

- Create: `src/teamster/code_locations/kippmiami/extracts/config/focus.yaml`
- Modify: `src/teamster/code_locations/kippmiami/extracts/assets.py`
- Modify: `src/teamster/code_locations/kippmiami/extracts/jobs.py`
- Modify: `src/teamster/code_locations/kippmiami/extracts/schedules.py`

**Interfaces:**

- Consumes: the `ssh_focus` resource (Task 1); the trimmed
  `kippmiami_extracts.rpt_focus__*` tables (Tasks 2-6).
- Produces: five assets `kippmiami/extracts/focus/<stem>_csv`, a job
  `kippmiami__extracts__focus__asset_job`, and a STOPPED schedule
  `focus_extract_assets_schedule`, all auto-collected by `definitions.py` via
  `extracts.schedules` and `load_assets_from_modules`.

> **Filename + path are unconfirmed (Open items in the spec).** The values below
> (`stem` = lowercase layout name, `path: incoming`) are working defaults.
> Confirm the exact filenames Focus expects and the incoming directory with
> Ops/registrar before the schedule is enabled; they are trivial YAML edits. The
> schedule ships STOPPED, so these defaults cannot push anything until someone
> enables it.

- [ ] **Step 1: Create `config/focus.yaml`**

Create `src/teamster/code_locations/kippmiami/extracts/config/focus.yaml`:

```yaml
assets:
  - query_config:
      type: schema
      value:
        table:
          schema: kippmiami_extracts
          name: rpt_focus__demographics
    file_config:
      stem: demographics
      suffix: csv
      format:
        header_replacements:
          stdt_id: STDT_ID
          last_name: LAST_NAME
          first_name: FIRST_NAME
          name_suffix: NAME_SUFFIX
          middle_name: MIDDLE_NAME
          nickname: NICKNAME
          dt_birth: DT_BIRTH
          gender: GENDER
          lang: LANG
          stdt_email: STDT_EMAIL
          ethnic_hl: ETHNIC_HL
          single_ethnic: SINGLE_ETHNIC
          race_am_ind_ak_nat: RACE_AM_IND_AK_NAT
          race_asian: RACE_ASIAN
          race_black: RACE_BLACK
          race_nat_haw_pac_isl: RACE_NAT_HAW_PAC_ISL
          race_white: RACE_WHITE
          residence_county: RESIDENCE_COUNTY
          contry_birth: CONTRY_BIRTH
          homeroom_tchr: HOMEROOM_TCHR
          resident_st: RESIDENT_ST
          birth_loc: BIRTH_LOC
          bdate_verif: BDATE_VERIF
          immun_st: IMMUN_ST
          primary_home_lang: PRIMARY_HOME_LANG
          native_parent_lang: NATIVE_PARENT_LANG
          grde_enter_dist: GRDE_ENTER_DIST
          msix_id: MSIX_ID
          homeroom: HOMEROOM
          pmrn: PMRN
          internt_perm: INTERNT_PERM
          act_perm: ACT_PERM
          direct_perm: DIRECT_PERM
          screen_perm: SCREEN_PERM
          photo_vid_perm: PHOTO_VID_PERM
          survey_perm: SURVEY_PERM
          mckay_sch_attend: MCKAY_SCH_ATTEND
          fhsaa_el3_ind: FHSAA_EL3_IND
          fhsaa_el3ch_ind: FHSAA_EL3CH_IND
          dt_home_lang_survey: DT_HOME_LANG_SURVEY
          casas_track: CASAS_TRACK
          lcp_cont_stdt: LCP_CONT_STDT
    destination_config:
      name: focus
      path: incoming
  - query_config:
      type: schema
      value:
        table:
          schema: kippmiami_extracts
          name: rpt_focus__student_enrollment
    file_config:
      stem: student_enrollment
      suffix: csv
      format:
        header_replacements:
          syear: SYEAR
          school_id: SCHOOL_ID
          student_id: STUDENT_ID
          grade_id: GRADE_ID
          start_date: START_DATE
          enrollment_code: ENROLLMENT_CODE
          end_date: END_DATE
          drop_code: DROP_CODE
          calendar_id: CALENDAR_ID
          prior_dist: PRIOR_DIST
          prior_state: PRIOR_STATE
          prior_country: PRIOR_COUNTRY
          ed_choice: ED_CHOICE
          stdt_dis_affect: STDT_DIS_AFFECT
          offender_transfer_stdt: OFFENDER_TRANSFER_STDT
          came_from: CAME_FROM
          moved_to: MOVED_TO
          sec_sch: SEC_SCH
          grde_prom_st: GRDE_PROM_ST
          good_cause_exempt: GOOD_CAUSE_EXEMPT
          graduation_requirement_program: GRADUATION_REQUIREMENT_PROGRAM
          next_school: NEXT_SCHOOL
          next_grade: NEXT_GRADE
          district_ood: DISTRICT_OOD
          sch_ood: SCH_OOD
          include_in_class_rank: INCLUDE_IN_CLASS_RANK
          fl_days_present: FL_DAYS_PRESENT
          fl_days_absent: FL_DAYS_ABSENT
    destination_config:
      name: focus
      path: incoming
  - query_config:
      type: schema
      value:
        table:
          schema: kippmiami_extracts
          name: rpt_focus__addresses
    file_config:
      stem: addresses
      suffix: csv
      format:
        header_replacements:
          student_id: STUDENT_ID
          address: ADDRESS
          address2: ADDRESS2
          city: CITY
          state: STATE
          zipcode: ZIPCODE
          phone: PHONE
          mailing: MAILING
          mail_address: MAIL_ADDRESS
          mail_address2: MAIL_ADDRESS2
          mail_city: MAIL_CITY
          mail_state: MAIL_STATE
    destination_config:
      name: focus
      path: incoming
  - query_config:
      type: schema
      value:
        table:
          schema: kippmiami_extracts
          name: rpt_focus__contacts
    file_config:
      stem: contacts
      suffix: csv
      format:
        header_replacements:
          student_id: STUDENT_ID
          student_relation: STUDENT_RELATION
          sort_order: SORT_ORDER
          first_name: FIRST_NAME
          middle_name: MIDDLE_NAME
          last_name: LAST_NAME
          resides_with_stud: RESIDES_WITH_STUD
          custody: CUSTODY
          emergency: EMERGENCY
          pickup: PICKUP
          address: ADDRESS
          address2: ADDRESS2
          city: CITY
          state: STATE
          zipcode: ZIPCODE
          email: EMAIL
          contact1_type: CONTACT1_TYPE
          contact1_value: CONTACT1_VALUE
          contact1_blocked: CONTACT1_BLOCKED
          contact1_unlisted: CONTACT1_UNLISTED
          contact1_callout: CONTACT1_CALLOUT
          contact2_type: CONTACT2_TYPE
          contact2_value: CONTACT2_VALUE
          contact2_blocked: CONTACT2_BLOCKED
          contact2_unlisted: CONTACT2_UNLISTED
          contact2_callout: CONTACT2_CALLOUT
          contact3_type: CONTACT3_TYPE
          contact3_value: CONTACT3_VALUE
          contact3_blocked: CONTACT3_BLOCKED
          contact3_unlisted: CONTACT3_UNLISTED
          contact3_callout: CONTACT3_CALLOUT
          contact4_type: CONTACT4_TYPE
          contact4_value: CONTACT4_VALUE
          contact4_blocked: CONTACT4_BLOCKED
          contact4_unlisted: CONTACT4_UNLISTED
          contact4_callout: CONTACT4_CALLOUT
          contact5_type: CONTACT5_TYPE
          contact5_value: CONTACT5_VALUE
          contact5_blocked: CONTACT5_BLOCKED
          contact5_unlisted: CONTACT5_UNLISTED
          contact5_callout: CONTACT5_CALLOUT
          contact6_type: CONTACT6_TYPE
          contact6_value: CONTACT6_VALUE
          contact6_blocked: CONTACT6_BLOCKED
          contact6_unlisted: CONTACT6_UNLISTED
          contact6_callout: CONTACT6_CALLOUT
          contact7_type: CONTACT7_TYPE
          contact7_value: CONTACT7_VALUE
          contact7_blocked: CONTACT7_BLOCKED
          contact7_unlisted: CONTACT7_UNLISTED
    destination_config:
      name: focus
      path: incoming
  - query_config:
      type: schema
      value:
        table:
          schema: kippmiami_extracts
          name: rpt_focus__linked_students
    file_config:
      stem: linked_students
      suffix: csv
      format:
        header_replacements:
          primary_student_id: PRIMARY_STUDENT_ID
          secondary_student_id: SECONDARY_STUDENT_ID
    destination_config:
      name: focus
      path: incoming
```

- [ ] **Step 2: Wire the assets in `assets.py`**

Replace the contents of
`src/teamster/code_locations/kippmiami/extracts/assets.py` with:

```python
import pathlib

from dagster import config_from_files

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.extracts.assets import build_bigquery_query_sftp_asset

config_dir = pathlib.Path(__file__).parent / "config"

powerschool_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/powerschool.yaml"])["assets"]
]

focus_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/focus.yaml"])["assets"]
]

assets = [
    *powerschool_extract_assets,
    *focus_extract_assets,
]
```

- [ ] **Step 3: Add the job in `jobs.py`**

Append to `src/teamster/code_locations/kippmiami/extracts/jobs.py`:

```python
from teamster.code_locations.kippmiami.extracts.assets import focus_extract_assets

focus_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__focus__asset_job",
    selection=focus_extract_assets,
)
```

(Merge the new `import` with the existing
`from ...extracts.assets import powerschool_extract_assets` line into one import
statement.)

- [ ] **Step 4: Add the schedule in `schedules.py`**

In `src/teamster/code_locations/kippmiami/extracts/schedules.py`, import the new
job and append the schedule to the `schedules` list:

```python
from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.extracts.jobs import (
    focus_extract_asset_job,
    powerschool_extract_asset_job,
)

powerschool_extract_assets_schedule = ScheduleDefinition(
    job=powerschool_extract_asset_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

focus_extract_assets_schedule = ScheduleDefinition(
    job=focus_extract_asset_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    powerschool_extract_assets_schedule,
    focus_extract_assets_schedule,
]
```

- [ ] **Step 5: Verify the module imports and definitions load**

Run: `uv run python -c "import teamster.code_locations.kippmiami.definitions"`
Expected: exits 0, no traceback.

Run:
`uv run dagster definitions validate -m teamster.code_locations.kippmiami.definitions`
Expected: validation passes. If it errors only on missing env vars (codespace
has no `FOCUS_SFTP_*`), that is the known false positive — the import check
above is authoritative.

- [ ] **Step 6: Confirm the five asset keys exist**

Run:
`uv run python -c "from teamster.code_locations.kippmiami.extracts.assets import focus_extract_assets; print([a.key.to_user_string() for a in focus_extract_assets])"`
Expected: prints five keys — `kippmiami/extracts/focus/demographics_csv`,
`.../student_enrollment_csv`, `.../addresses_csv`, `.../contacts_csv`,
`.../linked_students_csv`.

- [ ] **Step 7: Commit**

```bash
git add src/teamster/code_locations/kippmiami/extracts/config/focus.yaml \
  src/teamster/code_locations/kippmiami/extracts/assets.py \
  src/teamster/code_locations/kippmiami/extracts/jobs.py \
  src/teamster/code_locations/kippmiami/extracts/schedules.py
git commit -m "feat(dagster): add Focus SFTP extract assets and daily schedule (#4207)"
```

---

## Post-implementation (out of plan scope, do not enable yet)

The schedule ships STOPPED. Before Ops enables it in Dagster Cloud, these must
be in place (see spec _Dependencies_ and _Open items_):

- `STDT_ID` populated (#4205) and the E05/E02 enrollment-code rule resolved
  (#4208).
- `FOCUS_SFTP_HOST` / `FOCUS_SFTP_USERNAME` / `FOCUS_SFTP_PASSWORD` provisioned
  in Dagster Cloud (confirm password vs key auth).
- Confirmed Focus filenames + incoming-directory path (update `stem` / `path` in
  `focus.yaml`).
- Focus sanity-check on the `contact7_callout` drop and the `resides_with_stud`
  required-but-null field.
