# Focus and Finalsite Sourcing for `rpt_gsheets__kippfwd_miami_roster` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-source `rpt_gsheets__kippfwd_miami_roster` from Focus and Finalsite
so it keeps producing data after Miami PowerSchool goes dark past
`academic_year = 2025`.

**Architecture:** A new kipptaf intermediate reads the Focus dlt landing tables
through the existing BQ-native `kippmiami_dlt_focus` source and produces one row
per student per school year. A second new intermediate ranks Finalsite guardians
1 and 2 per student. The reporting view joins both, keeps the existing FLDOE
FAST pivots, and retains one PowerSchool join for `previous_year_ada`.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, Dagster asset keys in source YAML,
sqlfluff and markdownlint via trunk.

- **Spec:**
  `docs/superpowers/specs/2026-08-10-focus-miami-kippfwd-roster-design.md`
- **Issue:** [#4782](https://github.com/TEAMSchools/teamster/issues/4782)

## Global Constraints

- **Worktree:** `/workspaces/teamster/.worktrees/focus-miami-kippfwd-roster`.
  Every `git` call uses `git -C <worktree>`; every `dbt` call uses
  `--project-dir <worktree>/src/dbt/kipptaf`. Read, Edit, and Write must target
  paths under the worktree, never `/workspaces/teamster/src/...`.
- **Never run bare `python` or `dbt`** — always `uv run dbt ...`.
- **`--state` must be the absolute main-repo path**
  `/workspaces/teamster/src/dbt/kipptaf/target/prod`. The relative form resolves
  under the worktree, which has no `target/prod/`.
- **The output contract does not change.** All 30 columns keep their existing
  names, types, and **select order**. The properties yml `columns:` block gains
  descriptions but no additions or removals.
- **SQL style** (`.trunk/config/.sqlfluff`): BigQuery dialect, trailing commas
  in `SELECT`, single quotes, 88-character lines, no `ORDER BY`, no
  `GROUP BY ALL`, no self-aliases (AL09).
- **ST09 join order:** ON-clause predicates put the earlier-referenced table on
  the left.
- **Do not run `trunk fmt`.** Run
  `/workspaces/teamster/.trunk/tools/trunk check --force <files>` with cwd set
  to the worktree — the binary lives only in the main repo, and relative paths
  run from the main repo check the wrong copies.
- **`current_academic_year` is 2025 and is stale** (it rolls each July; today is
  2026-08-10). Do not anchor the `enroll_status` derivation on that var — use
  the max `syear` present in Focus, per Task 3.

---

## File Structure

| File                                                                                             | Responsibility                                                                                                      |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/focus/sources-bigquery.yml`                                              | Declare the five additional Focus dlt landing tables                                                                |
| `src/dbt/kipptaf/models/focus/intermediate/int_focus__student_roster.sql`                        | Enrollment spine — one row per student per `syear`, with identity ids, gender, grade, `enroll_status`, `iep_status` |
| `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_roster.yml`             | Descriptions, PII tags, grain test                                                                                  |
| `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_guardians.sql`             | Guardian 1 and 2 per student, with typed phone slots resolved                                                       |
| `src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__student_guardians.yml`  | Descriptions, PII tags, grain test                                                                                  |
| `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql`            | Reporting view — joins the two intermediates, keeps the FAST pivots and the PowerSchool ADA join                    |
| `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__kippfwd_miami_roster.yml` | Contract columns plus descriptions and the scoped uniqueness test                                                   |

---

### Task 1: Declare the Focus source tables

**Files:**

- Modify: `src/dbt/kipptaf/models/focus/sources-bigquery.yml`

**Interfaces:**

- Consumes: nothing.
- Produces: `source("kippmiami_dlt_focus", "students")`,
  `source("kippmiami_dlt_focus", "school_gradelevels")`,
  `source("kippmiami_dlt_focus", "student_enrollment_codes")`,
  `source("kippmiami_dlt_focus", "custom_fields")`,
  `source("kippmiami_dlt_focus", "custom_field_select_options")`. Task 3
  consumes all five plus the already-declared
  `source("kippmiami_dlt_focus", "student_enrollment")`.

- [ ] **Step 1: Install packages in the fresh worktree**

A newly-created worktree has no `dbt_packages/`. Without this every later `dbt`
call fails with "N package(s) specified in packages.yml, but only 0 package(s)
installed".

```bash
uv run dbt deps \
  --project-dir /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster/src/dbt/kipptaf
```

Expected: `Installing ...` lines, then `Installed from version ...` per package.

- [ ] **Step 2: Add the five table entries**

Append these inside the existing `tables:` list in
`src/dbt/kipptaf/models/focus/sources-bigquery.yml`, after the
`student_enrollment` entry. Keep the existing three entries untouched.

**Indentation:** the block below is shown at column zero because the markdown
formatter normalizes it. In the real file every line needs six leading spaces so
`- name:` aligns with the existing `student_enrollment` entry under `tables:`.
Copying verbatim produces invalid YAML.

```yaml
- name: students
  description:
    Focus student records, one row per student. Wide custom_NNN columns carry
    the identity and demographic fields the KIPP Forward Miami roster reads.
  config:
    meta:
      dagster:
        asset_key:
          - kippmiami
          - dlt
          - focus
          - students
- name: school_gradelevels
  description:
    Focus grade-level definitions, one row per grade level per school.
    short_name is the zero-padded grade code, for example 07.
  config:
    meta:
      dagster:
        asset_key:
          - kippmiami
          - dlt
          - focus
          - school_gradelevels
- name: student_enrollment_codes
  description:
    Focus enrollment and withdrawal code definitions. type separates Add from
    Drop; short_name is the Florida DOE code such as E01 or W06.
  config:
    meta:
      dagster:
        asset_key:
          - kippmiami
          - dlt
          - focus
          - student_enrollment_codes
- name: custom_fields
  description:
    Focus custom-field definition catalog. Joined to custom_field_select_options
    to decode stored select values to labels and codes.
  config:
    meta:
      dagster:
        asset_key:
          - kippmiami
          - dlt
          - focus
          - custom_fields
- name: custom_field_select_options
  description:
    Allowed values for Focus select-type custom fields. code is the value Focus
    expects; label is the human-readable name.
  config:
    meta:
      dagster:
        asset_key:
          - kippmiami
          - dlt
          - focus
          - custom_field_select_options
```

- [ ] **Step 3: Verify the sources parse and resolve**

```bash
uv run dbt parse --target prod \
  --project-dir /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster/src/dbt/kipptaf
```

Expected: `Found N models, ... N sources ...` with no `Compilation Error`.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/focus/sources-bigquery.yml
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster add \
  src/dbt/kipptaf/models/focus/sources-bigquery.yml
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster commit \
  -m "feat(kipptaf): declare focus source tables for miami roster

Refs #4782"
```

---

### Task 2: Confirm the design spec and plan are committed

**Files:**

- Verify only:
  `docs/superpowers/specs/2026-08-10-focus-miami-kippfwd-roster-design.md`
- Verify only: `docs/superpowers/plans/2026-08-10-focus-miami-kippfwd-roster.md`

**Interfaces:**

- Consumes: nothing.
- Produces: nothing consumed by code.

Both documents were written and committed before implementation began. This task
is a gate, not new work — markdownlint fires only at pre-push and CI, so a
doc-only Trunk failure is easy to miss until the push is rejected.

- [ ] **Step 1: Confirm both files are committed and the tree is clean**

```bash
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster log --oneline -3
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster status --short
```

Expected: a `docs:` commit naming both files, and no unstaged changes under
`docs/superpowers/`. If either file is missing or dirty, commit it with
`git -C <worktree> add <paths>` and a `docs:` message referencing `#4782`.

- [ ] **Step 2: Re-lint both documents**

```bash
cd /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster
/workspaces/teamster/.trunk/tools/trunk check --force \
  docs/superpowers/specs/2026-08-10-focus-miami-kippfwd-roster-design.md \
  docs/superpowers/plans/2026-08-10-focus-miami-kippfwd-roster.md
```

Expected: no findings. The pre-commit `fmt` hook already resolved the prettier
table-alignment and MD060 table-column-style issues present at authoring time.
Any remaining MD040 (fenced block missing language), MD001 (heading increment),
or MD036 (bold used as heading) finding must be fixed and committed before
proceeding.

---

### Task 3: Build `int_focus__student_roster`

**Files:**

- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__student_roster.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_roster.yml`

**Interfaces:**

- Consumes: the six `kippmiami_dlt_focus` source tables from Task 1.
- Produces: `ref("int_focus__student_roster")` with columns `student_id`
  (INT64), `academic_year` (INT64), `lastfirst` (STRING), `ps_id` (INT64),
  `mdcps_id` (STRING), `fleid` (STRING), `gender` (STRING), `grade_level`
  (INT64), `enroll_status` (INT64), `iep_status` (STRING). Task 5 joins on
  `student_id`, `academic_year`, `ps_id`, and `fleid`.

- [ ] **Step 1: Write the model**

Create
`src/dbt/kipptaf/models/focus/intermediate/int_focus__student_roster.sql`:

```sql
with
    gender_options as (
        select o.id as option_id, o.code as gender_code,
        from {{ source("kippmiami_dlt_focus", "custom_field_select_options") }} as o
        inner join
            {{ source("kippmiami_dlt_focus", "custom_fields") }} as cf
            on o.source_id = cf.id
        where
            o.source_class = 'CustomField'
            and cf.deleted is null
            and cf.source_class = 'SISStudent'
            and lower(cf.column_name) = 'custom_200000000'
    ),

    focus_students as (
        select
            student_id,
            first_name,
            last_name,

            custom_l1482 as powerschool_id,
            custom_l1483 as disis_id,
            custom_200000224 as fleid,
            custom_200000000 as gender_option_id,
            custom_698 as ese_fefp_code,
        from {{ source("kippmiami_dlt_focus", "students") }}
        where deleted is null
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    enrollment_spans as (
        select
            e.student_id,
            e.syear,
            e.grade_id,
            e.start_date,

            dc.short_name as drop_code_short_name,
        from {{ source("kippmiami_dlt_focus", "student_enrollment") }} as e
        left join
            {{ source("kippmiami_dlt_focus", "student_enrollment_codes") }} as dc
            on e.drop_code = dc.id
            and dc.deleted is null
    ),

    canonical_enrollment as (
        {{
            dbt_utils.deduplicate(
                relation="enrollment_spans",
                partition_by="student_id, syear",
                order_by="start_date desc",
            )
        }}
    ),

    /* enroll_status anchors on the latest school year Focus holds rather than
       var("current_academic_year"), which lags the July rollover. PowerSchool
       enroll_status is a current-status value copied onto every historical row;
       this reproduces that semantic without depending on the var. */
    latest_syear as (
        select max(syear) as syear,
        from {{ source("kippmiami_dlt_focus", "student_enrollment") }}
    ),

    open_enrollment as (
        select distinct e.student_id,
        from {{ source("kippmiami_dlt_focus", "student_enrollment") }} as e
        inner join latest_syear as ly on e.syear = ly.syear
        where e.drop_code is null
    )

select
    ce.student_id,
    ce.syear as academic_year,

    s.fleid,

    gm.gender_code as gender,

    concat(s.last_name, ', ', s.first_name) as lastfirst,

    cast(s.powerschool_id as int64) as ps_id,
    cast(g.short_name as int64) as grade_level,

    lpad(cast(s.disis_id as string), 7, '0') as mdcps_id,

    if(s.ese_fefp_code is not null, 'Has IEP', 'No IEP') as iep_status,

    case
        when ce.start_date > current_date('{{ var("local_timezone") }}')
        then -1
        when ce.drop_code_short_name = 'W06'
        then 3
        when oe.student_id is not null
        then 0
        else 2
    end as enroll_status,
from canonical_enrollment as ce
inner join focus_students as s on ce.student_id = s.student_id
inner join
    {{ source("kippmiami_dlt_focus", "school_gradelevels") }} as g
    on ce.grade_id = g.id
left join gender_options as gm on s.gender_option_id = gm.option_id
left join open_enrollment as oe on ce.student_id = oe.student_id
```

- [ ] **Step 2: Write the properties yml**

Create
`src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_roster.yml`:

```yaml
models:
  - name: int_focus__student_roster
    description: >-
      Focus student roster, one row per student per school year. Collapses
      multiple enrollment spans within a year to the latest-starting span, and
      resolves the identity, demographic, and status fields the KIPP Forward
      Miami extract needs. Miami-only by construction — the kippmiami_dlt_focus
      source is a single-region landing dataset, so there is no
      _dbt_source_relation and no union join clause. Internal-only; a rpt_ view
      must sit between this model and any external consumer.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_id
              - academic_year
          config:
            severity: error
    columns:
      - name: student_id
        description: Focus student id. Grain key together with academic_year.
        config:
          meta:
            contains_pii: true
      - name: academic_year
        description: Focus syear, the school year start year, 2026 = 2026-27.
      - name: lastfirst
        description: Student name as last name, comma, first name.
        config:
          meta:
            contains_pii: true
      - name: ps_id
        description: >-
          PowerSchool student_number carried on the Focus student record. Null
          for students enrolled after the Focus cutover who were never assigned
          one, which also leaves them without a prior-year ADA value.
        config:
          meta:
            contains_pii: true
      - name: mdcps_id
        description: >-
          Miami-Dade County Public Schools student id, zero-padded to width 7.
          Focus stores it unpadded where PowerSchool stored it padded.
        config:
          meta:
            contains_pii: true
      - name: fleid
        description:
          Florida Education Identifier. Join key for FLDOE FAST scores.
        config:
          meta:
            contains_pii: true
      - name: gender
        description: >-
          Single-character gender code decoded from the Focus select option,
          matching the PowerSchool domain of M and F.
      - name: grade_level
        description: >-
          Numeric grade level, cast from the zero-padded Focus grade short name.
      - name: enroll_status
        description: >-
          PowerSchool-compatible status code. Minus 1 when the enrollment starts
          in the future, 3 on withdrawal code W06 for graduated with standard
          diploma, 0 when the student holds an open enrollment in the latest
          Focus school year, and 2 otherwise. Deliberately not derived from
          drop-code presence — Focus stamps W01 and W02 rollover codes on nearly
          every span at year end, so a presence test would read as a mass
          withdrawal.
      - name: iep_status
        description: >-
          Has IEP when the Focus ESE FEFP Code is populated, No IEP otherwise.
          This identifies roughly four fifths of the students PowerSchool
          flagged, so a No IEP value is not authoritative.
```

- [ ] **Step 3: Build the model and run its test**

```bash
uv run dbt build --select int_focus__student_roster \
  --project-dir /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster/src/dbt/kipptaf \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: `PASS` on the model and `PASS` on
`dbt_utils_unique_combination_of_columns_...`. A `unique_combination` failure
means the `dbt_utils.deduplicate` partition is wrong — it must be
`student_id, syear`, not the enrollment `id`.

- [ ] **Step 4: Verify `enroll_status` did not collapse**

This is the landmine check. Run against the dev schema the build just wrote
(substitute your own dev schema name, shown in the build output):

```sql
select academic_year, enroll_status, count(*) as n
from `teamster-332318`.`zz_<user>_kipptaf_focus`.`int_focus__student_roster`
where academic_year = 2025 and grade_level in (7, 8)
group by academic_year, enroll_status
```

Expected: roughly 222 rows at `enroll_status = 0` and 143 at `2`. If nearly all
365 land on `2`, the derivation is keying off drop-code presence — re-read the
`open_enrollment` CTE.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__student_roster.sql \
  src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_roster.yml
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster add \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__student_roster.sql \
  src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_roster.yml
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster commit \
  -m "feat(kipptaf): add int_focus__student_roster enrollment spine

Refs #4782"
```

---

### Task 4: Build `int_finalsite__student_guardians`

**Files:**

- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_guardians.sql`
- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__student_guardians.yml`

**Interfaces:**

- Consumes: `ref("stg_finalsite__contacts")`,
  `ref("stg_finalsite__contact_relationships")`,
  `ref("int_finalsite__contact_id_attributes")`.
- Produces: `ref("int_finalsite__student_guardians")` with columns
  `focus_student_id_prefixed` (STRING), `guardian_rank` (INT64), `guardian_name`
  (STRING), `guardian_email` (STRING), `phone_home` (STRING), `phone_mobile`
  (STRING). Task 5 joins on `focus_student_id_prefixed` and filters
  `guardian_rank` to 1 and 2.

- [ ] **Step 1: Write the model**

Create
`src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_guardians.sql`.
The rank window and the `rel_type` allowlist deliberately mirror
`rpt_focus__contacts` so the two models agree on who a guardian is.

```sql
with
    guardian_ranked as (
        select
            ida.focus_student_id_prefixed,

            g.first_name,
            g.last_name,
            g.email,
            g.phone_1_type,
            g.phone_1_number,
            g.phone_2_type,
            g.phone_2_number,

            row_number() over (
                partition by ida.focus_student_id_prefixed
                order by rel.is_primary desc, g.last_name asc, g.first_name asc
            ) as guardian_rank,
        from {{ ref("stg_finalsite__contact_relationships") }} as rel
        inner join
            {{ ref("stg_finalsite__contacts") }} as g
            on rel.rel_id = g.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as ida
            on rel.finalsite_enrollment_id = ida.finalsite_enrollment_id
        where
            ida.focus_student_id_prefixed is not null
            and rel.rel_type in (
                'parent',
                'guardian',
                'grandparent',
                'stepparent',
                'relative',
                'aunt/uncle'
            )
    )

select
    focus_student_id_prefixed,
    guardian_rank,

    email as guardian_email,

    concat(first_name, ' ', last_name) as guardian_name,

    case
        when phone_1_type = 'Home' then phone_1_number
        when phone_2_type = 'Home' then phone_2_number
    end as phone_home,

    case
        when phone_1_type = 'Cell' then phone_1_number
        when phone_2_type = 'Cell' then phone_2_number
    end as phone_mobile,
from guardian_ranked
where guardian_rank <= 2
```

- [ ] **Step 2: Write the properties yml**

Create
`src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__student_guardians.yml`:

```yaml
models:
  - name: int_finalsite__student_guardians
    description: >-
      The first two Finalsite guardians per student, keyed to the Focus student
      id. Ranking and the relationship-type allowlist mirror rpt_focus__contacts
      so both models agree on who counts as a guardian. Finalsite API ingestion
      is wired only for KIPP Miami today, so this model carries Miami rows only.
      Internal-only; a rpt_ view must sit between this model and any external
      consumer.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - focus_student_id_prefixed
              - guardian_rank
          config:
            severity: error
    columns:
      - name: focus_student_id_prefixed
        description: >-
          Focus student id as carried by int_finalsite__contact_id_attributes.
          Joins to int_focus__student_roster.student_id.
        config:
          meta:
            contains_pii: true
      - name: guardian_rank
        description: >-
          1 for the primary guardian, 2 for the next. Ordered by the Finalsite
          primary flag, then last name, then first name.
      - name: guardian_name
        description: Guardian first and last name.
        config:
          meta:
            contains_pii: true
      - name: guardian_email
        description: Guardian email address.
        config:
          meta:
            contains_pii: true
      - name: phone_home
        description: >-
          Guardian phone from whichever Finalsite slot is typed Home. Null when
          neither slot carries a Home number, which is common — most guardians
          record only a Cell number.
        config:
          meta:
            contains_pii: true
      - name: phone_mobile
        description: >-
          Guardian phone from whichever Finalsite slot is typed Cell.
        config:
          meta:
            contains_pii: true
```

- [ ] **Step 3: Build the model and run its test**

```bash
uv run dbt build --select int_finalsite__student_guardians \
  --project-dir /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster/src/dbt/kipptaf \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: `PASS` on the model and on its uniqueness test.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_guardians.sql \
  src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__student_guardians.yml
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster add \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_guardians.sql \
  src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__student_guardians.yml
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster commit \
  -m "feat(kipptaf): add int_finalsite__student_guardians

Refs #4782"
```

---

### Task 5: Rewrite the reporting view

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql`
  (full rewrite)
- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__kippfwd_miami_roster.yml`

**Interfaces:**

- Consumes: `ref("int_focus__student_roster")` and
  `ref("int_finalsite__student_guardians")` from Tasks 3 and 4,
  `ref("stg_fldoe__fast")`, `ref("int_extracts__student_enrollments")`.
- Produces: the unchanged 30-column contract consumed by the
  `gsheets__kippfwd_miami_roster` exposure.

- [ ] **Step 1: Open the two follow-up tracking issues**

The `TODO` comments in Step 2 must point at issues that stay open after this PR
merges. Create both before writing the SQL, and substitute the real numbers.

Issue A — title:
`feat(kipptaf): source advisory assignment for Miami grades 7-8`. Body: Focus
has no advisory structure for grades 7 and 8 — homeroom courses exist only for
K-5, `student_enrollment.team_id` is null for all students, and no grade 7-8
course functions as an advisory. `advisor_lastfirst` in
`rpt_gsheets__kippfwd_miami_roster` is cast null until a source exists. Labels:
`feat`, `dbt`, `kipptaf`, `focus`.

Issue B — title:
`feat(kipptaf): build Focus GPA so Miami roster GPA columns can be restored`.
Body: `gpa_cumulative` and `gpa_y1` in `rpt_gsheets__kippfwd_miami_roster` are
cast null because Focus `report_card_grades` holds roughly 1,300 rows and no GPA
model exists in the `focus` package. Labels: `feat`, `dbt`, `kipptaf`, `focus`.

- [ ] **Step 2: Rewrite the model**

Replace the entire contents of
`src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql`.
Replace `#AAAA` and `#BBBB` with the issue numbers from Step 1.

The `ST06` ignore is deliberate: the select order is the Google Sheet's column
order and must not be reshuffled to satisfy the linter.

```sql
with
    fast_concat as (
        select
            student_id,
            academic_year,

            concat(achievement_level, ' (', scale_score, ')') as fast_score,
            lower(concat(discipline, '_', administration_window)) as pivot_column,
        from {{ ref("stg_fldoe__fast") }}
    ),

    fast_pivot as (
        select
            student_id,
            academic_year,
            ela_pm1,
            ela_pm2,
            ela_pm3,
            math_pm1,
            math_pm2,
            math_pm3,
        from
            fast_concat pivot (
                max(fast_score) for pivot_column
                in ('ela_pm1', 'ela_pm2', 'ela_pm3', 'math_pm1', 'math_pm2', 'math_pm3')
            )
    ),

    guardian_1 as (
        select
            focus_student_id_prefixed,
            guardian_name,
            guardian_email,
            phone_home,
            phone_mobile,
        from {{ ref("int_finalsite__student_guardians") }}
        where guardian_rank = 1
    ),

    guardian_2 as (
        select
            focus_student_id_prefixed,
            guardian_name,
            guardian_email,
            phone_home,
            phone_mobile,
        from {{ ref("int_finalsite__student_guardians") }}
        where guardian_rank = 2
    )

-- trunk-ignore(sqlfluff/ST06): select order is the Google Sheet column order
select
    r.academic_year,
    r.lastfirst,

    /* TODO(#AAAA): Focus has no advisory structure for grades 7-8 */
    cast(null as string) as advisor_lastfirst,

    r.ps_id,
    r.mdcps_id,
    r.gender,
    r.iep_status,

    g1.guardian_name as contact_1_name,
    g1.phone_home as contact_1_phone_home,
    g1.phone_mobile as contact_1_phone_mobile,
    g1.guardian_email as contact_1_email_current,

    g2.guardian_name as contact_2_name,
    g2.phone_home as contact_2_phone_home,
    g2.phone_mobile as contact_2_phone_mobile,
    g2.guardian_email as contact_2_email_current,

    r.enroll_status,
    r.grade_level,

    fp.ela_pm1,
    fp.ela_pm2,
    fp.ela_pm3,
    fp.math_pm1,
    fp.math_pm2,
    fp.math_pm3,

    /* TODO(#BBBB): no Focus GPA model exists */
    cast(null as float64) as gpa_cumulative,

    ada.ada_unweighted_year_prev as previous_year_ada,

    r.fleid,

    /* TODO(#BBBB): no Focus GPA model exists */
    cast(null as float64) as gpa_y1,

    fp_prev.ela_pm3 as ela_pm3_prev,
    fp_prev.math_pm3 as math_pm3_prev,
from {{ ref("int_focus__student_roster") }} as r
left join
    fast_pivot as fp
    on r.fleid = fp.student_id
    and r.academic_year = fp.academic_year
left join
    fast_pivot as fp_prev
    on r.fleid = fp_prev.student_id
    and r.academic_year - 1 = fp_prev.academic_year
left join
    guardian_1 as g1
    on cast(r.student_id as string) = g1.focus_student_id_prefixed
left join
    guardian_2 as g2
    on cast(r.student_id as string) = g2.focus_student_id_prefixed
left join
    {{ ref("int_extracts__student_enrollments") }} as ada
    on r.ps_id = ada.student_number
    and r.academic_year = ada.academic_year
    and ada.region = 'Miami'
    and ada.rn_year = 1
where
    r.grade_level in (7, 8)
    and r.academic_year >= {{ var("current_academic_year") - 1 }}
```

- [ ] **Step 3: Add descriptions and the uniqueness test to the properties yml**

Keep every existing `- name:` / `data_type:` pair exactly as it is — the
contract must not change. Add a model-level `description:` and `data_tests:`
block above `columns:`, and a `description:` under each column.

The uniqueness test is scoped because the contract exposes no column that is
both unique and non-null: `ps_id` is null for post-cutover enrollees and `fleid`
is null for a handful of students.

```yaml
models:
  - name: rpt_gsheets__kippfwd_miami_roster
    description: >-
      KIPP Forward Miami grades 7 and 8 roster, one row per student per academic
      year for the current and prior year. Enrollment, identity, and
      demographics come from Focus; guardian contacts from Finalsite; FAST
      scores from FLDOE; and prior-year ADA from PowerSchool, which holds no
      Miami data past academic year 2025. Advisor and both GPA columns are cast
      null pending sources in Focus.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - academic_year
              - fleid
          config:
            severity: error
            where: fleid is not null
    columns:
      - name: academic_year
        description: School year start year, 2026 = 2026-27.
        data_type: int64
```

Continue the remaining 29 columns in their existing order, each keeping its
`data_type` and gaining a `description:`. Source each description from the
matching column in `int_focus__student_roster.yml` or
`int_finalsite__student_guardians.yml`. For the three null-cast columns, state
that the value is not currently sourced and why.

- [ ] **Step 4: Build the model and its test**

```bash
uv run dbt build --select rpt_gsheets__kippfwd_miami_roster \
  --project-dir /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster/src/dbt/kipptaf \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: `PASS` on the model and its uniqueness test. A contract error naming a
specific column means a `data_type` in the yml drifted from the SQL — the SQL
must change, not the contract.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql \
  src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__kippfwd_miami_roster.yml
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster add \
  src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__kippfwd_miami_roster.sql \
  src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__kippfwd_miami_roster.yml
git -C /workspaces/teamster/.worktrees/focus-miami-kippfwd-roster commit \
  -m "feat(kipptaf): source kippfwd miami roster from focus and finalsite

Closes #4782"
```

---

### Task 6: Parity verification

**Files:**

- No file changes. This task gates the PR.

**Interfaces:**

- Consumes: the dev-schema build of `rpt_gsheets__kippfwd_miami_roster` from
  Task 5.
- Produces: nothing. Its output is a go or no-go on opening the PR.

- [ ] **Step 1: Confirm row-count parity for the PowerSchool-era year**

Substitute your dev schema. The prod side is the current model, still
PowerSchool-sourced at this point.

```sql
select
    'new' as build,
    academic_year,
    count(*) as n
from `teamster-332318`.`zz_<user>_kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster`
where academic_year = 2025
group by build, academic_year
union all
select
    'prod' as build,
    academic_year,
    count(*) as n
from `teamster-332318`.`kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster`
where academic_year = 2025
group by build, academic_year
```

Expected: 365 on both sides. A shortfall on the new side points at the inner
join to `focus_students`, which drops enrollments whose student row is
soft-deleted.

- [ ] **Step 2: Re-confirm the three identity match rates**

```sql
select
    count(*) as n,
    countif(n.ps_id = p.ps_id) as ps_id_match,
    countif(n.fleid = p.fleid) as fleid_match,
    countif(n.mdcps_id = p.mdcps_id) as mdcps_id_match
from `teamster-332318`.`zz_<user>_kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster` as n
inner join
    `teamster-332318`.`kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster` as p
    on n.ps_id = p.ps_id
    and n.academic_year = p.academic_year
where n.academic_year = 2025
```

Expected: `ps_id_match` equal to `n`, `fleid_match` at or above 360, and
`mdcps_id_match` at or above 356. The four `mdcps_id` misses are rows where
PowerSchool stored an unpadded 6-character value.

- [ ] **Step 3: Confirm the SY2026 rows exist**

This is the whole point of the change and cannot be checked against prod, which
has no such rows.

```sql
select academic_year, grade_level, count(*) as n
from `teamster-332318`.`zz_<user>_kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster`
where academic_year = 2026
group by academic_year, grade_level
```

Expected: roughly 188 in grade 7 and 167 in grade 8. Zero rows means the
`academic_year >= current_academic_year - 1` filter excluded them because the
`current_academic_year` var is still 2025 — that is correct behavior for today,
and 2026 rows appear once the var rolls. Note the result either way in the PR
body.

- [ ] **Step 4: Confirm guardian coverage**

```sql
select
    count(*) as n,
    countif(contact_1_name is not null) as c1_name,
    countif(contact_1_email_current is not null) as c1_email,
    countif(contact_2_name is not null) as c2_name,
    countif(contact_1_phone_mobile is not null) as c1_mobile,
    countif(contact_1_phone_home is not null) as c1_home
from `teamster-332318`.`zz_<user>_kipptaf_extracts`.`rpt_gsheets__kippfwd_miami_roster`
where academic_year = 2026
```

Expected: `c1_name` near 364, `c1_email` near 355, `c2_name` near 255,
`c1_mobile` well above `c1_home`. A low `c1_home` is expected, not a bug.

- [ ] **Step 5: Open the pull request**

Use `.github/pull_request_template.md` as the body. Include the Step 1 through
Step 4 numbers, and call out explicitly that `advisor_lastfirst`,
`gpa_cumulative`, and `gpa_y1` now return null, with links to the two follow-up
issues from Task 5 Step 1. Reference `Closes #4782`.

Do not run `gh project item-add` on the PR — the issue reference in the body
puts it on the board.

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: the source declaration to
Task 1, the Focus column mapping and both derivations to Task 3, the Finalsite
contacts to Task 4, the null casts and retained PowerSchool join to Task 5, the
test table to Tasks 3 through 5, and the manual verification list to Task 6. The
spec's "Out of scope" items intentionally have no task.

**Type consistency.** `int_focus__student_roster` emits `academic_year` (aliased
from `syear`) and Task 5 joins on `r.academic_year` — consistent.
`int_finalsite__student_guardians.focus_student_id_prefixed` is STRING while
`int_focus__student_roster.student_id` is INT64, so Task 5 casts on the join.
`ps_id` is INT64 on both sides of the ADA join to `student_number`.

**Known soft spot.** Task 5 Step 3 describes the remaining 29 column
descriptions rather than spelling out all 29. They are mechanical restatements
of descriptions written verbatim in Tasks 3 and 4, and the existing yml already
holds every name and `data_type`.
