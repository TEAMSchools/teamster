# Finalsite → Focus output models (Component 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape the staged Finalsite enrollment data into the five Focus-SIS
SFTP import templates (Demographics, Student_Enrollment, Addresses, Contacts,
Linked_Students), keyed on `STDT_ID`, as contract-enforced `kippmiami` dbt
models — plus the four Google-Sheets value crosswalks they depend on.

**Architecture:** Finalsite is the system of record. Staging
(`stg_finalsite__contacts`, `stg_finalsite__contact_relationships`,
`stg_finalsite__status_report`) plus the existing
`int_finalsite__enrollment_lifecycle` classifier feed five `rpt_finalsite__*`
output models in `kippmiami/models/extracts/finalsite/`. Each output model emits
the **full Focus template column set in exact left-to-right order**, populating
what Finalsite supplies and emitting typed `NULL` for the FL-specific columns we
have no source for. Value translation (Finalsite grade/school/status/withdrawal
→ Focus codes) is done via four Google-Sheets crosswalks declared in `kipptaf`
(the project wired for Sheet ingestion) and consumed cross-project. Component 5
(the `build_bigquery_query_sftp_asset` transport that writes these tables to
Focus's SFTP) is **out of scope** — a separate plan.

**Tech Stack:** dbt (BigQuery), dbt unit tests, Google Sheets external sources,
Dagster (asset auto-discovery only — no new Dagster code in this plan).

---

## Decisions baked into this plan

1. **Build in `kippmiami`, not `kipptaf`.** Unlike the PowerSchool autocomm
   extracts (heavy model in `kipptaf`, thin region-filtered wrapper in the
   district), the Finalsite data is Miami-only and already district-local
   (`int_finalsite__enrollment_lifecycle` lives in `kippmiami`). The output
   models source it directly — no cross-project wrapper, no
   `home_work_location_dagster_code_location` filter.
2. **Full template column set, in exact order, NULL where unsourced.** Honors
   Focus's "column order, headers, and sort are required to match" guideline.
3. **Crosswalks in `kipptaf` google_sheets, consumed cross-project.** `kipptaf`
   is the only code location with Google-Sheets ingestion wired
   (`src/teamster/code_locations/kipptaf/google/sheets/assets.py` auto-discovers
   `GOOGLE_SHEETS` external sources from the manifest). `kippmiami` declares a
   `kipptaf_google_sheets` cross-project source over the resulting staging
   tables (mirrors the existing `kipptaf_extracts` pattern).
4. **Crosswalk plumbing now; ops populates values later.** Sheets are created
   with header rows and the mappings we already know (grade short names;
   `new`→`EA1` / `returning`→`RA1`); `SCH_ID` and `DROP_CODE` cells are left for
   Miami ops to fill. Crosswalk-join coverage tests are **warn** severity until
   populated, so the project still builds.
5. **Output logic is validated by dbt unit tests** that mock the upstream refs —
   the reshaping is verified now without waiting on live Sheet ingestion.

## Assumptions & flags (resolve during implementation; do not block)

These are the cells where the Finalsite source value is not yet confirmed for
the Miami tenant. Each is emitted with the best-known expression and flagged;
none blocks the build.

- **`STDT_ID` source field.** The minted 10-digit id lives in the
  `id_attributes` array under a per-tenant `field_name`. This plan introduces a
  `kippmiami` var `finalsite_focus_student_id_field` (default `"focus_id"` —
  **confirm the real Miami field name**). New enrollees have no minted id until
  Finalsite's autogen `IdField` is configured (Finalsite-side prereq); returning
  students are populated today.
- **`GENDER` encoding.** `stg_finalsite__contacts.gender` stored form is mapped
  `Male`/`M`→`M`, `Female`/`F`→`F`, else `NULL`. Confirm the raw values.
- **Race flags (`RACE_*`, `ETHNIC_HL`, `SINGLE_ETHNIC`).** `ETHNIC_HL` is
  sourced from the confirmed `custom_attributes` field `latino_hispanic_yn`
  (boolean → `Y`/`N`). `RACE_*` derive from the confirmed `race_ms` multi-select
  custom field, but `race_ms`'s **option values are not yet confirmed** for
  Miami — emitted `NULL` pending a follow-up race-value mapping. `SINGLE_ETHNIC`
  `NULL`.
- **`assigned_school_ss`** is the confirmed Miami custom field for school of
  enrollment; it feeds the school crosswalk. Confirm its emitted values match
  the crosswalk keys.

---

## File Structure

**Create (kipptaf — crosswalk plumbing):**

- `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__focus__grade_crosswalk.sql`
- `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__focus__school_crosswalk.sql`
- `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__focus__enrollment_code_crosswalk.sql`
- `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__focus__drop_code_crosswalk.sql`
- the matching four `.../staging/properties/*.yml`

**Modify (kipptaf):**

- `src/dbt/kipptaf/models/google/sheets/sources-external.yml` (4 new source
  table blocks)

**Create (kippmiami — output models):**

- `src/dbt/kippmiami/models/extracts/finalsite/rpt_finalsite__demographics.sql`
  (+ properties yml + unit test)
- `.../rpt_finalsite__student_enrollment.sql` (+ yml + unit test)
- `.../rpt_finalsite__addresses.sql` (+ yml + unit test)
- `.../rpt_finalsite__contacts.sql` (+ yml + unit test)
- `.../rpt_finalsite__linked_students.sql` (+ yml + unit test)

**Modify (kippmiami):**

- `src/dbt/kippmiami/models/extracts/sources.yml` (new `kipptaf_google_sheets`
  cross-project source with the 4 crosswalk tables)
- `src/dbt/kippmiami/dbt_project.yml` (add `finalsite_focus_student_id_field`
  var)

**Manual prerequisite (executor or ops):**

- One Google Sheet ("KIPP Miami | Finalsite→Focus Crosswalks") with four tabs,
  header rows, and known mappings filled. Capture its URL for the
  `sources-external.yml` `uris` entries.

---

## Task 0: Crosswalk Google Sheet (prerequisite — owned by Charlie/ops)

**Files:** none (external artifact). **Not built by this plan's implementer.**
Charlie creates the Sheet before the PR using the data below; until then Task 1
commits a clearly-marked placeholder URL. The dbt code is validated offline by
the per-model unit tests, so the missing Sheet does not block any task.

Create a Google Sheet titled `KIPP Miami | Finalsite→Focus Crosswalks` with four
tabs named exactly (these become the `sheet_range` values). Share it with the
BigQuery external-connection service account (copy the share from any sheet in
`kipptaf/models/google/sheets/sources-external.yml`), then record the URL and
replace the Task 1 placeholder.

The key values below are pulled from live Miami staging
(`kippmiami_finalsite.*`, 2026-06-17) — real, not assumed.

**Tab `src_focus__grade_crosswalk`** — header `finalsite_grade_canonical_name`,
`focus_grade_id`:

| finalsite_grade_canonical_name | focus_grade_id (confirm vs Focus grade-level short names) |
| ------------------------------ | --------------------------------------------------------- |
| `k`                            | `KG`                                                      |
| `1st`                          | `1`                                                       |
| `2nd`                          | `2`                                                       |
| `3rd`                          | `3`                                                       |
| `4th`                          | `4`                                                       |
| `5th`                          | `5`                                                       |
| `6th`                          | `6`                                                       |
| `7th`                          | `7`                                                       |
| `8th`                          | `8`                                                       |
| `9th`                          | `9`                                                       |

(Miami is K–9 today; add `10th`–`12th` as grades roll up.)

**Tab `src_focus__enrollment_code_crosswalk`** — header
`finalsite_lifecycle_action`, `focus_enrollment_code` (keyed on
`lifecycle_action`, NOT `enrollment_type` — `enrollment_type` is NULL on most
in-scope `create` rows):

| finalsite_lifecycle_action | focus_enrollment_code                       |
| -------------------------- | ------------------------------------------- |
| `create`                   | `EA1` (confirm)                             |
| `re_enroll`                | `RA1` (confirm)                             |
| `transfer_out`             | (ops — add code on the existing enrollment) |

**Tab `src_focus__school_crosswalk`** — header `finalsite_assigned_school`,
`focus_school_id` (ops fills `focus_school_id` = Focus `SCH_ID`):

| finalsite_assigned_school | focus_school_id                                        |
| ------------------------- | ------------------------------------------------------ |
| `KIPP Royalty Academy`    | (ops)                                                  |
| `KIPP Courage Academy`    | (ops)                                                  |
| `KIPP Miami Tech`         | (ops)                                                  |
| `KIPP Legacy Elementary`  | (ops)                                                  |
| `KIPP Legacy Middle`      | (ops)                                                  |
| `KIPP Miami Courage`      | (ops — likely a data-entry variant of Courage Academy) |
| `KIPP Miami Royalty`      | (ops — likely a data-entry variant of Royalty Academy) |

(19 in-scope rows have a NULL `assigned_school` — they will not join; surfaced
by the warn-severity coverage test.)

**Tab `src_focus__drop_code_crosswalk`** — header `finalsite_withdrawal_reason`,
`focus_drop_code` (ops fills `focus_drop_code` = Focus Drop code, e.g. `W05`):

| finalsite_withdrawal_reason | focus_drop_code |
| --------------------------- | --------------- |
| `mid_year_withdrawal`       | (ops)           |
| `summer_withdraw`           | (ops)           |
| `not_enrolling`             | (ops)           |

> No commit in this task — it produces the URL that replaces the Task 1
> placeholder before the PR.

---

## Task 1: Declare the four crosswalk sources (kipptaf)

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml`

- [ ] **Step 1: Append four source table blocks.** The Sheet does not exist yet
      (Task 0 is owned by Charlie). Use the literal placeholder
      `https://docs.google.com/spreadsheets/d/REPLACE_WITH_CROSSWALK_SHEET_ID`
      for every `uris` entry, and add a YAML comment
      `# TODO(#4073): replace with crosswalk Sheet URL before merge` above the
      first block. Pattern mirrors the existing
      `src_google_sheets__coupa__school_name_crosswalk` block. The placeholder
      does not affect `dbt parse`; live ingestion waits on the real URL.

```yaml
# TODO(#4073): replace with crosswalk Sheet URL before merge
- name: src_google_sheets__focus__grade_crosswalk
  external:
    options:
      format: GOOGLE_SHEETS
      uris:
        - https://docs.google.com/spreadsheets/d/REPLACE_WITH_CROSSWALK_SHEET_ID
      sheet_range: src_focus__grade_crosswalk
      skip_leading_rows: 1
  columns:
    - name: finalsite_grade_canonical_name
      data_type: string
    - name: focus_grade_id
      data_type: string
  config:
    meta:
      dagster:
        asset_key: [kipptaf, google, sheets, focus, grade_crosswalk]
- name: src_google_sheets__focus__school_crosswalk
  external:
    options:
      format: GOOGLE_SHEETS
      uris:
        - https://docs.google.com/spreadsheets/d/REPLACE_WITH_CROSSWALK_SHEET_ID
      sheet_range: src_focus__school_crosswalk
      skip_leading_rows: 1
  columns:
    - name: finalsite_assigned_school
      data_type: string
    - name: focus_school_id
      data_type: string
  config:
    meta:
      dagster:
        asset_key: [kipptaf, google, sheets, focus, school_crosswalk]
- name: src_google_sheets__focus__enrollment_code_crosswalk
  external:
    options:
      format: GOOGLE_SHEETS
      uris:
        - https://docs.google.com/spreadsheets/d/REPLACE_WITH_CROSSWALK_SHEET_ID
      sheet_range: src_focus__enrollment_code_crosswalk
      skip_leading_rows: 1
  columns:
    - name: finalsite_lifecycle_action
      data_type: string
    - name: focus_enrollment_code
      data_type: string
  config:
    meta:
      dagster:
        asset_key: [kipptaf, google, sheets, focus, enrollment_code_crosswalk]
- name: src_google_sheets__focus__drop_code_crosswalk
  external:
    options:
      format: GOOGLE_SHEETS
      uris:
        - https://docs.google.com/spreadsheets/d/REPLACE_WITH_CROSSWALK_SHEET_ID
      sheet_range: src_focus__drop_code_crosswalk
      skip_leading_rows: 1
  columns:
    - name: finalsite_withdrawal_reason
      data_type: string
    - name: focus_drop_code
      data_type: string
  config:
    meta:
      dagster:
        asset_key: [kipptaf, google, sheets, focus, drop_code_crosswalk]
```

- [ ] **Step 2: Verify the YAML parses + sources resolve.**

Run:
`DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-output/src/dbt/kipptaf`
Expected: parses with no error; the four new sources appear.

- [ ] **Step 3: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-output add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-output commit -m "feat(finalsite): declare focus crosswalk google_sheets sources"
```

---

## Task 2: Crosswalk staging models (kipptaf)

**Files (create):**

- `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__focus__grade_crosswalk.sql`
- `.../stg_google_sheets__focus__school_crosswalk.sql`
- `.../stg_google_sheets__focus__enrollment_code_crosswalk.sql`
- `.../stg_google_sheets__focus__drop_code_crosswalk.sql`
- the four matching `properties/*.yml`

- [ ] **Step 1: Write the four staging models.** Each is a passthrough (matches
      the existing `stg_google_sheets__coupa__school_name_crosswalk` pattern):

```sql
select *,
from {{ source("google_sheets", "src_google_sheets__focus__grade_crosswalk") }}
```

(repeat for `school_crosswalk`, `enrollment_code_crosswalk`,
`drop_code_crosswalk`, each pointing at its matching source).

- [ ] **Step 2: Write the four properties YAML** declaring columns +
      `unique`/`not_null` on the Finalsite key column. Example for grade:

```yaml
models:
  - name: stg_google_sheets__focus__grade_crosswalk
    columns:
      - name: finalsite_grade_canonical_name
        data_type: string
        data_tests:
          - not_null
          - unique
      - name: focus_grade_id
        data_type: string
```

(school keyed on `finalsite_assigned_school`; enrollment_code on
`finalsite_lifecycle_action`; drop_code on `finalsite_withdrawal_reason`.)

- [ ] **Step 3: Verify parse.** Run the Task 1 Step 2 `dbt parse` command;
      expect the four models to resolve. (A live `dbt build` requires the Sheet
      ingested — deferred; covered by output-model unit tests instead.)

- [ ] **Step 4: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-output add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-output commit -m "feat(finalsite): add focus crosswalk staging models"
```

---

## Task 3: Cross-project source + var (kippmiami)

**Files:**

- Modify: `src/dbt/kippmiami/models/extracts/sources.yml`
- Modify: `src/dbt/kippmiami/dbt_project.yml`

- [ ] **Step 1: Add the `kipptaf_google_sheets` cross-project source.** Append
      to `kippmiami/models/extracts/sources.yml` (mirrors the `kipptaf_extracts`
      block already there). **Verify the exact `asset_key` path** against the
      kipptaf staging models with
      `uv run dbt ls --project-dir .../src/dbt/kipptaf --select stg_google_sheets__focus__grade_crosswalk --output json`
      and adjust if the derived key differs from the template below.

```yaml
- name: kipptaf_google_sheets
  tables:
    - name: stg_google_sheets__focus__grade_crosswalk
      config:
        meta:
          dagster:
            group: google_sheets
            asset_key:
              [
                kipptaf,
                google,
                sheets,
                staging,
                stg_google_sheets__focus__grade_crosswalk,
              ]
    - name: stg_google_sheets__focus__school_crosswalk
      config:
        meta:
          dagster:
            group: google_sheets
            asset_key:
              [
                kipptaf,
                google,
                sheets,
                staging,
                stg_google_sheets__focus__school_crosswalk,
              ]
    - name: stg_google_sheets__focus__enrollment_code_crosswalk
      config:
        meta:
          dagster:
            group: google_sheets
            asset_key:
              [
                kipptaf,
                google,
                sheets,
                staging,
                stg_google_sheets__focus__enrollment_code_crosswalk,
              ]
    - name: stg_google_sheets__focus__drop_code_crosswalk
      config:
        meta:
          dagster:
            group: google_sheets
            asset_key:
              [
                kipptaf,
                google,
                sheets,
                staging,
                stg_google_sheets__focus__drop_code_crosswalk,
              ]
```

- [ ] **Step 2: Add the var.** Under `vars:` in `kippmiami/dbt_project.yml`:

```yaml
finalsite_focus_student_id_field: focus_id
```

- [ ] **Step 3: Verify parse.** Run:
      `DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-output/src/dbt/kippmiami`
      Expected: parses; `source("kipptaf_google_sheets", ...)` resolves.

- [ ] **Step 4: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-output add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-output commit -m "feat(finalsite): wire kippmiami to focus crosswalks + student-id var"
```

---

## Shared building blocks (used by Tasks 4–8)

These CTE fragments recur across the output models. Define them per-model (dbt
has no shared-CTE include); they are written out in full here so each task is
self-contained.

**`stdt_id` resolution** (pivot the minted id out of `id_attributes`):

```sql
(
    select av.value.string_value,
    from unnest(c.id_attributes) as av
    where av.field_name = '{{ var("finalsite_focus_student_id_field") }}'
    limit 1
) as stdt_id
```

**In-scope filter** — the output models cover the set the lifecycle model
already classifies. Join `int_finalsite__enrollment_lifecycle` (grain =
`finalsite_enrollment_id`) and keep its rows (it already applies the
eligibility + transfer-out predicate).

**`latino_hispanic_yn`** (pivot a boolean custom attribute):

```sql
(
    select av.value.boolean_value,
    from unnest(c.custom_attributes) as av
    where av.field_name = 'latino_hispanic_yn'
    limit 1
) as is_latino_hispanic
```

---

## Task 4: `rpt_finalsite__student_enrollment` (the core model)

**Files:**

- Create:
  `src/dbt/kippmiami/models/extracts/finalsite/rpt_finalsite__student_enrollment.sql`
- Create: `.../properties/rpt_finalsite__student_enrollment.yml`
- Test: `.../properties/rpt_finalsite__student_enrollment.yml` (unit test block)

Grain: one row per in-scope enrollment (`finalsite_enrollment_id`). Emit all 29
`STUDENT_ENROLLMENT_LAYOUT` columns in order. `END_DATE`/`DROP_CODE` populate
only for `lifecycle_action = 'transfer_out'`.

- [ ] **Step 1: Write the failing unit test.** Mock `id_attributes`, the
      lifecycle model, status_report, and the grade/school/enrollment_code/
      drop_code crosswalks; assert the 5 required columns + `ENROLLMENT_CODE` +
      transfer-out `END_DATE`/`DROP_CODE`.

```yaml
unit_tests:
  - name: test_student_enrollment_shape
    model: rpt_finalsite__student_enrollment
    given:
      - input: ref('stg_finalsite__contacts')
        rows:
          - {
              finalsite_enrollment_id: e1,
              school_year_start: 2025,
              grade_canonical_name: "05",
              id_attributes: [],
            }
      - input: ref('int_finalsite__enrollment_lifecycle')
        rows:
          - {
              finalsite_enrollment_id: e1,
              lifecycle_action: create,
              assigned_school: "North",
              enrollment_start_date: 2025-08-12,
              enrollment_end_date,
              withdrawal_reason,
              enrollment_type: new,
            }
      - input:
          source('kipptaf_google_sheets',
          'stg_google_sheets__focus__grade_crosswalk')
        rows: [{ finalsite_grade_canonical_name: "05", focus_grade_id: "5" }]
      - input:
          source('kipptaf_google_sheets',
          'stg_google_sheets__focus__school_crosswalk')
        rows: [{ finalsite_assigned_school: "North", focus_school_id: "0001" }]
      - input:
          source('kipptaf_google_sheets',
          'stg_google_sheets__focus__enrollment_code_crosswalk')
        rows:
          [{ finalsite_lifecycle_action: create, focus_enrollment_code: EA1 }]
      - input:
          source('kipptaf_google_sheets',
          'stg_google_sheets__focus__drop_code_crosswalk')
        rows:
          [
            {
              finalsite_withdrawal_reason: mid_year_withdrawal,
              focus_drop_code: W05,
            },
          ]
    expect:
      rows:
        - {
            SYEAR: 2025,
            SCHOOL_ID: "0001",
            STUDENT_ID,
            GRADE_ID: "5",
            START_DATE: "20250812",
            ENROLLMENT_CODE: EA1,
            END_DATE,
            DROP_CODE,
          }
```

> Fixtures are UNQUOTED except leading-zero strings (`"05"`, `"0001"`) — quote
> those or yamllint `octal-values` fails CI. Add a second mocked enrollment
> (`lifecycle_action: transfer_out`, a withdrawal date) asserting `END_DATE` and
> `DROP_CODE` populate.

- [ ] **Step 2: Run it to confirm it fails** (model doesn't exist):
      `DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt test --select rpt_finalsite__student_enrollment --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-output/src/dbt/kippmiami`
      Expected: compilation/selection error.

- [ ] **Step 3: Write the model.** Column order is authoritative.

```sql
with
    enrollment as (
        select
            c.finalsite_enrollment_id,
            (
                select av.value.string_value,
                from unnest(c.id_attributes) as av
                where
                    av.field_name
                    = '{{ var("finalsite_focus_student_id_field") }}'
                limit 1
            ) as stdt_id,
            l.school_year_start,
            l.assigned_school,
            l.grade_canonical_name,
            l.lifecycle_action,
            l.enrollment_start_date,
            l.enrollment_end_date,
            l.withdrawal_reason,
        from {{ ref("stg_finalsite__contacts") }} as c
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on c.finalsite_enrollment_id = l.finalsite_enrollment_id
    )

select
    e.school_year_start as syear,
    sch.focus_school_id as school_id,
    e.stdt_id as student_id,
    gr.focus_grade_id as grade_id,
    format_date('%Y%m%d', e.enrollment_start_date) as start_date,
    ec.focus_enrollment_code as enrollment_code,
    if(
        e.lifecycle_action = 'transfer_out',
        format_date('%Y%m%d', e.enrollment_end_date),
        cast(null as string)
    ) as end_date,
    if(
        e.lifecycle_action = 'transfer_out', dc.focus_drop_code, cast(null as string)
    ) as drop_code,
    cast(null as string) as calendar_id,
    cast(null as string) as prior_dist,
    cast(null as string) as prior_state,
    cast(null as string) as prior_country,
    cast(null as string) as ed_choice,
    cast(null as string) as stdt_dis_affect,
    cast(null as string) as offender_transfer_stdt,
    cast(null as string) as came_from,
    cast(null as string) as moved_to,
    cast(null as string) as sec_sch,
    cast(null as string) as grde_prom_st,
    cast(null as string) as good_cause_exempt,
    cast(null as string) as graduation_requirement_program,
    cast(null as string) as next_school,
    cast(null as string) as next_grade,
    cast(null as string) as district_ood,
    cast(null as string) as sch_ood,
    cast(null as string) as include_in_class_rank,
    cast(null as int64) as fl_days_present,
    cast(null as int64) as fl_days_absent,
    cast(null as int64) as fl_days_absent_not_disc,
from enrollment as e
left join
    {{ source("kipptaf_google_sheets", "stg_google_sheets__focus__grade_crosswalk") }}
        as gr
    on e.grade_canonical_name = gr.finalsite_grade_canonical_name
left join
    {{ source("kipptaf_google_sheets", "stg_google_sheets__focus__school_crosswalk") }}
        as sch
    on e.assigned_school = sch.finalsite_assigned_school
left join
    {{
        source(
            "kipptaf_google_sheets",
            "stg_google_sheets__focus__enrollment_code_crosswalk",
        )
    }} as ec
    on e.lifecycle_action = ec.finalsite_lifecycle_action
left join
    {{ source("kipptaf_google_sheets", "stg_google_sheets__focus__drop_code_crosswalk") }}
        as dc
    on e.withdrawal_reason = dc.finalsite_withdrawal_reason
```

> dbt model output column names are lowercased; the Focus header (`SYEAR`,
> `SCHOOL_ID`, …) is applied at transport time via `file_config.format`
> `header_replacements` (Component 5). Keep dbt names lowercase snake_case to
> satisfy sqlfluff. **Column ORDER here must equal the Focus layout order.**

- [ ] **Step 4: Write the contract YAML** — declare all 29 columns with
      `data_type`, in order; `unique`+`not_null` on `student_id`; `not_null` on
      `syear`/`school_id`/`grade_id`/`start_date` (warn — depends on crosswalk
      population); `relationships`-style coverage from the model to each
      crosswalk at **warn** severity.

- [ ] **Step 5: Run the unit test to pass:** Task 4 Step 2 command. Expected:
      PASS.

- [ ] **Step 6: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-output add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-output commit -m "feat(finalsite): add rpt_finalsite__student_enrollment focus output"
```

---

## Task 5: `rpt_finalsite__demographics`

**Files:** `.../rpt_finalsite__demographics.sql` + properties yml + unit test.

Grain: one row per in-scope student (`finalsite_enrollment_id`). 43 columns in
`DEMOGRAPHICS_LAYOUT` order. Per-column source:

| #   | Column               | Source expression                                                                          |
| --- | -------------------- | ------------------------------------------------------------------------------------------ |
| 1   | STDT_ID              | `id_attributes` pivot (shared block)                                                       |
| 2   | LAST_NAME            | `c.last_name`                                                                              |
| 3   | FIRST_NAME           | `c.first_name`                                                                             |
| 4   | NAME_SUFFIX          | `cast(null as string)`                                                                     |
| 5   | MIDDLE_NAME          | `c.middle_name`                                                                            |
| 6   | NICKNAME             | `c.preferred_name`                                                                         |
| 7   | DT_BIRTH             | `format_date('%Y%m%d', c.birth_date)`                                                      |
| 8   | GENDER               | `case when c.gender in ('M','Male') then 'M' when c.gender in ('F','Female') then 'F' end` |
| 9   | LANG                 | `cast(null as string)`                                                                     |
| 10  | STDT_EMAIL           | `c.email`                                                                                  |
| 11  | ETHNIC_HL            | `if(latino_hispanic pivot, 'Y', 'N')`                                                      |
| 12  | SINGLE_ETHNIC        | `cast(null as string)`                                                                     |
| 13  | RACE_AM_IND_AK_NAT   | `cast(null as string)` (race_ms values TBD)                                                |
| 14  | RACE_ASIAN           | `cast(null as string)`                                                                     |
| 15  | RACE_BLACK           | `cast(null as string)`                                                                     |
| 16  | RACE_NAT_HAW_PAC_ISL | `cast(null as string)`                                                                     |
| 17  | RACE_WHITE           | `cast(null as string)`                                                                     |
| 18  | RESIDENCE_COUNTY     | `cast(null as string)`                                                                     |
| 19  | CONTRY_BIRTH         | `cast(null as string)`                                                                     |
| 20  | HOMEROOM_TCHR        | `cast(null as string)`                                                                     |
| 21  | RESIDENT_ST          | `cast(null as string)`                                                                     |
| 22  | BIRTH_LOC            | `cast(null as string)`                                                                     |
| 23  | BDATE_VERIF          | `cast(null as string)`                                                                     |
| 24  | IMMUN_ST             | `cast(null as string)`                                                                     |
| 25  | PRIMARY_HOME_LANG    | `cast(null as string)`                                                                     |
| 26  | NATIVE_PARENT_LANG   | `cast(null as string)`                                                                     |
| 27  | GRDE_ENTER_DIST      | `cast(null as string)`                                                                     |
| 28  | MSIX_ID              | `cast(null as string)`                                                                     |
| 29  | HOMEROOM             | `cast(null as string)`                                                                     |
| 30  | PMRN                 | `cast(null as string)`                                                                     |
| 31  | INTERNT_PERM         | `cast(null as string)`                                                                     |
| 32  | ACT_PERM             | `cast(null as string)`                                                                     |
| 33  | DIRECT_PERM          | `cast(null as string)`                                                                     |
| 34  | SCREEN_PERM          | `cast(null as string)`                                                                     |
| 35  | PHOTO_VID_PERM       | `cast(null as string)`                                                                     |
| 36  | SURVEY_PERM          | `cast(null as string)`                                                                     |
| 37  | MCKAY_SCH_ATTEND     | `cast(null as string)`                                                                     |
| 38  | FHSAA_EL3_IND        | `cast(null as string)`                                                                     |
| 39  | FHSAA_EL3CH_IND      | `cast(null as string)`                                                                     |
| 40  | DT_HOME_LANG_SURVEY  | `cast(null as string)`                                                                     |
| 41  | CASAS_TRACK          | `cast(null as string)`                                                                     |
| 42  | LCP_CONT_STDT        | `cast(null as string)`                                                                     |
| 43  | TIDE_ACCESS_CODE     | `cast(null as string)`                                                                     |

- [ ] **Step 1:** Write the failing unit test (mock contacts incl. a populated
      `latino_hispanic_yn` custom attribute + `id_attributes`; assert STDT_ID,
      names, `DT_BIRTH` format, `GENDER` map, `ETHNIC_HL`).
- [ ] **Step 2:** Run to confirm fail.
- [ ] **Step 3:** Write the model (43 columns in order, per the table;
      `from stg_finalsite__contacts inner join int_finalsite__enrollment_lifecycle`).
- [ ] **Step 4:** Write the contract YAML (43 columns + `unique`/`not_null` on
      `stdt_id`).
- [ ] **Step 5:** Run unit test to pass.
- [ ] **Step 6:** Commit
      (`feat(finalsite): add rpt_finalsite__demographics focus output`).

---

## Task 6: `rpt_finalsite__addresses`

**Files:** `.../rpt_finalsite__addresses.sql` + properties yml + unit test.

Grain: one row per in-scope student. 13 columns in `ADDRESS_LAYOUT` order:

| #   | Column        | Source                 |
| --- | ------------- | ---------------------- |
| 1   | STUDENT_ID    | `id_attributes` pivot  |
| 2   | ADDRESS       | `c.address_1`          |
| 3   | ADDRESS2      | `c.address_2`          |
| 4   | CITY          | `c.city`               |
| 5   | STATE         | `c.state`              |
| 6   | ZIPCODE       | `c.zip`                |
| 7   | PHONE         | `c.phone_1_number`     |
| 8   | MAILING       | `cast(null as string)` |
| 9   | MAIL_ADDRESS  | `cast(null as string)` |
| 10  | MAIL_ADDRESS2 | `cast(null as string)` |
| 11  | MAIL_CITY     | `cast(null as string)` |
| 12  | MAIL_STATE    | `cast(null as string)` |
| 13  | MAIL_ZIPCODE  | `cast(null as string)` |

- [ ] **Step 1–6:** failing unit test (assert address columns map) → confirm
      fail → model (13 cols in order) → contract YAML (`unique`/`not_null` on
      `student_id`) → pass → commit
      (`feat(finalsite): add rpt_finalsite__addresses focus output`).

---

## Task 7: `rpt_finalsite__contacts`

**Files:** `.../rpt_finalsite__contacts.sql` + properties yml + unit test.

Grain: **one row per (student, guardian)** — multiple rows per student, one per
contact. Source: `stg_finalsite__contact_relationships` (guardian edges,
`rel_type in ('parent','guardian')`) joined `rel_id → stg_finalsite__contacts`
for the guardian's name/email/phone; the student's `STDT_ID` from the student
contact's `id_attributes`. 51 columns in `CONTACTS_LAYOUT` order. `SORT_ORDER` =
`is_primary desc` ranking. The `CONTACT{1,2}_*` blocks map the guardian's two
phones; `CONTACT3..7` are `NULL`.

| #     | Column                                            | Source                                                       |
| ----- | ------------------------------------------------- | ------------------------------------------------------------ |
| 1     | STUDENT_ID                                        | student `id_attributes` pivot                                |
| 2     | STUDENT_RELATION                                  | `rel.rel_type`                                               |
| 3     | SORT_ORDER                                        | `row_number()` over student ordered by `rel.is_primary desc` |
| 4     | FIRST_NAME                                        | guardian `g.first_name`                                      |
| 5     | MIDDLE_NAME                                       | `g.middle_name`                                              |
| 6     | LAST_NAME                                         | `g.last_name`                                                |
| 7     | RESIDES_WITH_STUD                                 | `cast(null as string)` (no source → default; flag)           |
| 8     | CUSTODY                                           | `cast(null as string)`                                       |
| 9     | EMERGENCY                                         | `cast(null as string)`                                       |
| 10    | PICKUP                                            | `cast(null as string)`                                       |
| 11    | ADDRESS                                           | `g.address_1`                                                |
| 12    | ADDRESS2                                          | `g.address_2`                                                |
| 13    | CITY                                              | `g.city`                                                     |
| 14    | STATE                                             | `g.state`                                                    |
| 15    | ZIPCODE                                           | `g.zip`                                                      |
| 16    | EMAIL                                             | `g.email`                                                    |
| 17    | CONTACT1_TYPE                                     | `g.phone_1_type`                                             |
| 18    | CONTACT1_VALUE                                    | `g.phone_1_number`                                           |
| 19–21 | CONTACT1_BLOCKED/UNLISTED/CALLOUT                 | `cast(null as string)`                                       |
| 22    | CONTACT2_TYPE                                     | `g.phone_2_type`                                             |
| 23    | CONTACT2_VALUE                                    | `g.phone_2_number`                                           |
| 24–26 | CONTACT2\_\*                                      | `cast(null as string)`                                       |
| 27–51 | CONTACT3..7 (TYPE/VALUE/BLOCKED/UNLISTED/CALLOUT) | `cast(null as string)`                                       |

- [ ] **Step 1:** Write the failing unit test — mock a student with two guardian
      relationships (`is_primary` true/false) and the guardian contact rows;
      assert two output rows with `SORT_ORDER` 1/2, names, `CONTACT1_VALUE` =
      phone.
- [ ] **Step 2:** Confirm fail.
- [ ] **Step 3:** Write the model. Skeleton:

```sql
with
    student as (
        select
            c.finalsite_enrollment_id,
            (
                select av.value.string_value,
                from unnest(c.id_attributes) as av
                where
                    av.field_name
                    = '{{ var("finalsite_focus_student_id_field") }}'
                limit 1
            ) as stdt_id,
        from {{ ref("stg_finalsite__contacts") }} as c
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on c.finalsite_enrollment_id = l.finalsite_enrollment_id
    ),

    guardians as (
        select
            rel.finalsite_enrollment_id,
            rel.rel_type,
            rel.is_primary,
            g.first_name,
            g.middle_name,
            g.last_name,
            g.email,
            g.address_1,
            g.address_2,
            g.city,
            g.state,
            g.zip,
            g.phone_1_type,
            g.phone_1_number,
            g.phone_2_type,
            g.phone_2_number,
        from {{ ref("stg_finalsite__contact_relationships") }} as rel
        inner join
            {{ ref("stg_finalsite__contacts") }} as g
            on rel.rel_id = g.finalsite_enrollment_id
        where rel.rel_type in ('parent', 'guardian')
    )

select
    s.stdt_id as student_id,
    g.rel_type as student_relation,
    row_number() over (
        partition by g.finalsite_enrollment_id order by g.is_primary desc
    ) as sort_order,
    g.first_name,
    g.middle_name,
    g.last_name,
    -- ... remaining 45 columns in CONTACTS_LAYOUT order per the table above
from student as s
inner join guardians as g on s.finalsite_enrollment_id = g.finalsite_enrollment_id
```

- [ ] **Step 4:** Contract YAML — 51 columns;
      `dbt_utils.unique_combination_of_columns` on `[student_id, sort_order]`;
      `not_null` on `student_id`/`first_name`/`last_name`/`sort_order`.
- [ ] **Step 5:** Run unit test to pass.
- [ ] **Step 6:** Commit
      (`feat(finalsite): add rpt_finalsite__contacts focus output`).

---

## Task 8: `rpt_finalsite__linked_students`

**Files:** `.../rpt_finalsite__linked_students.sql` + properties yml + unit
test.

Grain: one row per sibling pair (`PRIMARY_STUDENT_ID`, `SECONDARY_STUDENT_ID`).
Source: `stg_finalsite__contact_relationships` with `rel_type = 'sibling'`. Both
sides must resolve to a minted `STDT_ID` (drop pairs where the sibling is
outside the pulled cohort / has no id). 3 columns in `LINKED_STUDENTS` order:

| #   | Column               | Source                                              |
| --- | -------------------- | --------------------------------------------------- |
| 1   | PRIMARY_STUDENT_ID   | student `id_attributes` pivot                       |
| 2   | SECONDARY_STUDENT_ID | sibling (`rel_id` → contacts) `id_attributes` pivot |
| 3   | RELATIONSHIP         | `'sibling'` (literal; valid Focus value)            |

- [ ] **Step 1:** Failing unit test — two students linked as siblings, both with
      minted ids → one (or two, if both directions emitted) output row(s).
      Decide direction: emit a single primary→secondary row per unordered pair
      (dedupe with `where primary_student_id < secondary_student_id`).
- [ ] **Step 2:** Confirm fail.
- [ ] **Step 3:** Write the model (join `contact_relationships` sibling edges →
      student id pivot on both sides; filter both ids `is not null`; dedupe pair
      direction).
- [ ] **Step 4:** Contract YAML — 3 columns;
      `dbt_utils.unique_combination_of_columns` on
      `[primary_student_id, secondary_student_id]`; `not_null` on all three;
      `accepted_values` on `relationship`
      (`[sibling, step_sibling, cousin, parent]`).
- [ ] **Step 5:** Run unit test to pass.
- [ ] **Step 6:** Commit
      (`feat(finalsite): add rpt_finalsite__linked_students focus output`).

---

## Task 9: Full-project parse + project config

**Files:** none (verification) — unless the new dir needs a `dbt_project.yml`
entry.

- [ ] **Step 1: Confirm the new models inherit the `extracts` contract.** They
      live under `models/extracts/finalsite/`, and `dbt_project.yml` sets
      `extracts: +schema: extracts` + `+contract: enforced: true` at the
      `extracts` level — so they are contract-enforced and land in the
      `extracts` schema with no additional config. Verify with
      `dbt ls --select rpt_finalsite__*` that schema + contract resolve.
- [ ] **Step 2: Full parse of both projects:**
      `DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt parse --project-dir .../src/dbt/kippmiami`
      and the same for `kipptaf`. Expected: no errors.
- [ ] **Step 3: Run all five unit tests together:**
      `DBT_PROFILES_DIR=/workspaces/teamster/.dbt uv run dbt test --select rpt_finalsite__* --project-dir .../src/dbt/kippmiami`
      Expected: all unit tests PASS.
- [ ] **Step 4: Trunk check** every changed/created `.sql`, `.yml`, `.md` from
      inside the worktree with the absolute trunk binary.
- [ ] **Step 5: Commit** any config fix
      (`chore(finalsite): focus output model project config`).

---

## Out of scope (follow-up plans)

- **Component 5 — transport.** A `config/finalsite.yaml` driving five
  `build_bigquery_query_sftp_asset` calls in
  `src/teamster/code_locations/kippmiami/extracts/assets.py`, the Focus SFTP
  `ssh_*` resource in `definitions.py`, static filenames
  (`Demographics`/`Student_Enrollment_<YYYY-ZZZZ>`/`Addresses`/`Contacts`/
  `Linked_Students`), `header_replacements` to apply the exact Focus headers,
  and the run schedule.
- **Race/ethnicity mapping** — a `race_ms` value→`RACE_*` crosswalk once Miami's
  option values are confirmed.
- **Component 3 — identity crosswalk & write-back** — matching returning
  students to existing Focus records; persisting
  `finalsite_contact_id ↔ student_id ↔ focus_uuid`.
