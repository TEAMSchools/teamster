# Amplify package intermediates: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the Amplify-only value logic in the `amplify` package, alias the
frozen API archive to the live SFTP column names once at kipptaf, and add the
uniqueness tests that make a resumed Paterson feed fail loudly.

**Architecture:** Two value-only edits to the package PM staging model
(`device_date` fallback, unique surrogate key). Two new kipptaf `select *`
wrappers rename the archive's API columns to SFTP names. The two kipptaf mClass
intermediates then become union plus crosswalk plus Focus offset. Three
consumers inside `models/amplify/` read the renamed columns; nothing outside
changes.

**Tech Stack:** dbt-core on BigQuery, `dbt_utils` (`union_relations`,
`generate_surrogate_key`, `unique_combination_of_columns`), `uv`, trunk.

Spec:
`docs/superpowers/specs/2026-09-14-amplify-package-intermediates-design.md`.
Issue: #5305.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-amplify-package-intermediates`.
  Every git call is `git -C <worktree>`; every path is under the worktree. Bash
  cwd does not persist: prefix `cd <worktree> &&` in the same command.
- Open files under `src/dbt/` with the Read tool, never `cat`. Edit them with
  Edit or Write.
- Always `uv run dbt ...` with `--project-dir <worktree>/src/dbt/<project>` and
  `--profiles-dir /workspaces/teamster/.dbt`. Never `uv --directory`.
- `--state` is the MAIN repo's prod manifest, absolute:
  `/workspaces/teamster/src/dbt/<project>/target/prod`.
- Live SFTP column names win. The archive is aliased at kipptaf. Renames are
  `except (...)` plus `<old> as <new>`; same-name value swaps are `replace`.
  BigQuery rejects a rename inside `replace`.
- No lateral column aliases in a `select` list. No `qualify`, no `order by`.
- Package staging tests carry `config: severity: error`.
- PII: model-level `config: meta: contains_pii: true` on the 3 package staging
  models and the 2 new kipptaf API wrappers.
- Commit messages are conventional commits, end with
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`, and reference
  `Refs #5305`. Stage with explicit paths, never `git add -A`.
- Before pushing, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.
- Never emit student-level values anywhere outbound. Counts only.

---

### Task 0: Install packages in the worktree

**Files:** none edited.

- [ ] **Step 1: `dbt deps` for the three projects**

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-amplify-package-intermediates
for p in kippnewark kipppaterson kipptaf; do
  uv run dbt deps --project-dir "$wt/src/dbt/$p" --profiles-dir /workspaces/teamster/.dbt
done
```

Expected: each ends `Installing ...` with no error. A fresh worktree has no
`dbt_packages/`, and every later build fails without this.

---

### Task 1: Package PM staging: `device_date` fallback, unique key, tests, PII tags

**Files:**

- Modify:
  `src/dbt/amplify/models/mclass/sftp/staging/stg_amplify__mclass__sftp__pm_student_summary.sql`
- Modify:
  `src/dbt/amplify/models/mclass/sftp/staging/properties/stg_amplify__mclass__sftp__pm_student_summary.yml`
- Modify:
  `src/dbt/amplify/models/mclass/sftp/staging/properties/stg_amplify__mclass__sftp__benchmark_student_summary.yml`
- Modify:
  `src/dbt/amplify/models/mclass/sftp/staging/properties/stg_amplify__mclass__sftp__pm_student_summary_aimline.yml`

**Interfaces:**

- Produces: `stg_amplify__mclass__sftp__pm_student_summary.device_date` is never
  null where `sync_date` is set; `surrogate_key` is unique per row. Column set
  unchanged, so no contract change.

- [ ] **Step 1: Rewrite the PM staging SQL**

Replace the file's contents. The `normalized` CTE is unchanged from today; the
two lower blocks move the fallback into `replace` and the key into the final
select, where it can see the coalesced `device_date`.

```sql
with
    normalized as (
        select
            * except (
                device_date,
                student_primary_id_studentnumber,
                probe_number,
                score,
                additional_student_id_primarysisid,
                sync_date,
                total_number_of_probes,
                measure,
                school_primary_id
            ),

            cast(probe_number as int) as probe_number,
            cast(
                additional_student_id_primarysisid as int
            ) as additional_student_id_primarysisid,
            cast(total_number_of_probes as int) as total_number_of_probes,

            cast(score as numeric) as measure_standard_score,

            cast(device_date as date) as device_date,
            cast(sync_date as date) as sync_date,

            cast(
                cast(student_primary_id_studentnumber as numeric) as int
            ) as student_primary_id_studentnumber,

            cast(school_primary_id as int) as school_primary_id,

            cast(left(school_year, 4) as int) as academic_year,

            if(
                assessment_grade = 'K', 0, cast(assessment_grade as int)
            ) as assessment_grade_int,

            if(
                enrollment_grade = 'K', 0, cast(enrollment_grade as int)
            ) as enrollment_grade_int,

            case
                measure
                when 'Maze'
                then 'Reading Comprehension (Maze)'
                when 'NWF-WRC'
                then 'Decoding (NWF-WRC)'
                when 'NWF-CLS'
                then 'Letter Sounds (NWF-CLS)'
                when 'ORF'
                then 'Reading Fluency (ORF)'
                when 'ORF-Accu'
                then 'Reading Accuracy (ORF-Accu)'
                when 'WRF'
                then 'Word Reading (WRF)'
                when 'PSF'
                then 'Phonemic Awareness (PSF)'
                when '(DEC-IW)'
                then 'Irregular Words (DEC-IW)'
                else measure
            end as measure,

        from {{ source("amplify_mclass_sftp", "pm_student_summary") }}
    ),

    pm_student_summary as (
        select
            -- Amplify leaves device_date blank on some rows; the sync date is
            -- the closest thing to when the probe happened.
            * replace (coalesce(device_date, sync_date) as device_date),

            case
                measure
                when 'Composite'
                then 'Composite'
                when 'Decoding (NWF-WRC)'
                then 'NWF'
                when 'Irregular Words (DEC-IW)'
                then 'DEC'
                when 'Letter Names (LNF)'
                then 'LNF'
                when 'Letter Sounds (NWF-CLS)'
                then 'NWF'
                when 'Phonemic Awareness (PSF)'
                then 'PSF'
                when 'Reading Accuracy (ORF-Accu)'
                then 'ORF'
                when 'Reading Comprehension (Maze)'
                then 'Comprehension'
                when 'Reading Fluency (ORF)'
                then 'ORF'
                when 'Word Reading (WRF)'
                then 'WRF'
            end as measure_name_code,

        from normalized
    )

select
    *,

    case
        measure_name_code
        when 'Comprehension'
        then 'Comprehension'
        when 'DEC'
        then 'Irregular Words'
        when 'LNF'
        then 'Letter Names'
        when 'NWF'
        then 'Nonsense Word Fluency'
        when 'ORF'
        then 'Oral Reading Fluency'
        when 'PSF'
        then 'Phonological Awareness'
        when 'WRF'
        then 'Word Reading Fluency'
        else measure_name_code
    end as measure_name,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_primary_id_studentnumber",
                "school_year",
                "pm_period",
                "measure",
                "probe_number",
                "device_date",
                "assessment_grade",
            ]
        )
    }} as surrogate_key,

from pm_student_summary
```

- [ ] **Step 2: Update the PM staging YAML**

In `stg_amplify__mclass__sftp__pm_student_summary.yml`:

Add directly under `- name: stg_amplify__mclass__sftp__pm_student_summary`,
before `columns:`:

```yaml
description: >-
  Amplify mCLASS DIBELS progress monitoring scores from the PM SFTP file. One
  row per student, school year, PM period, measure, probe, device date and
  assessment grade. The file is a network-wide export of the Amplify account, so
  a district's copy can carry other regions' schools.
config:
  meta:
    contains_pii: true
```

Move the `surrogate_key` column block (today at line 157) to the top of
`columns:` (per-column tests sort first) and replace it with:

```yaml
- name: surrogate_key
  data_type: string
  description: >-
    Hash of student_primary_id_studentnumber, school_year, pm_period, measure,
    probe_number, device_date and assessment_grade. One per row.
  data_tests:
    - unique:
        config:
          severity: error
```

Replace the `device_date` block (today at line 105) with:

```yaml
- name: device_date
  data_type: date
  description: >-
    Date the probe was administered on the device. Falls back to sync_date where
    Amplify left it blank.
```

- [ ] **Step 3: Update the benchmark staging YAML**

In `stg_amplify__mclass__sftp__benchmark_student_summary.yml`, add under
`- name: stg_amplify__mclass__sftp__benchmark_student_summary`, before
`columns:`:

```yaml
description: >-
  Amplify mCLASS DIBELS benchmark scores from the SFTP file. One row per
  student, school year, benchmark period and assessment grade. The file is a
  network-wide export of the Amplify account, so a district's copy can carry
  other regions' schools.
config:
  meta:
    contains_pii: true
```

Move the `surrogate_key` block (today at line 276) to the top of `columns:` and
replace it with:

```yaml
- name: surrogate_key
  data_type: string
  description: >-
    Hash of student_primary_id_studentnumber, school_year, benchmark_period and
    assessment_grade. One per row.
  data_tests:
    - unique:
        config:
          severity: error
```

- [ ] **Step 4: Tag the aimline staging YAML**

In `stg_amplify__mclass__sftp__pm_student_summary_aimline.yml`, add after the
model `description:` block and before `columns:`:

```yaml
config:
  meta:
    contains_pii: true
```

Also give its existing `- unique` on `surrogate_key` the error severity:

```yaml
data_tests:
  - unique:
      config:
        severity: error
```

- [ ] **Step 5: Stage your dev copy of the PM external, both districts**

Personal `zz_cbini_*` schema, not classifier-blocked.

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-amplify-package-intermediates
for p in kippnewark kipppaterson; do
  uv run dbt run-operation stage_external_sources \
    --args "select: amplify_mclass_sftp.pm_student_summary" \
    --vars '{ext_full_refresh: true}' \
    --target dev --project-dir "$wt/src/dbt/$p" --profiles-dir /workspaces/teamster/.dbt
done
```

Expected: `1 SOURCES ... 1 TABLE` created per district, no error.

- [ ] **Step 6: Build the PM staging model in dev, both districts, tests
      included**

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-amplify-package-intermediates
for p in kippnewark kipppaterson; do
  uv run dbt build --select stg_amplify__mclass__sftp__pm_student_summary \
    --target dev --project-dir "$wt/src/dbt/$p" --profiles-dir /workspaces/teamster/.dbt \
    --defer --state "/workspaces/teamster/src/dbt/$p/target/prod"
done
```

Expected: model builds (contract passes, since the column set is unchanged) and
`unique_stg_amplify__mclass__sftp__pm_student_summary_surrogate_key` PASSES in
both districts. Also run the benchmark and aimline tests against the deferred
prod relations, no build needed:

```bash
uv run dbt test --select stg_amplify__mclass__sftp__benchmark_student_summary stg_amplify__mclass__sftp__pm_student_summary_aimline \
  --target dev --project-dir "$wt/src/dbt/kippnewark" --profiles-dir /workspaces/teamster/.dbt \
  --defer --state /workspaces/teamster/src/dbt/kippnewark/target/prod
```

Expected: both `unique` tests PASS.

- [ ] **Step 7: Confirm the fallback and key in the warehouse**

Via the BigQuery MCP:

```sql
select
    count(*) as n,
    count(distinct surrogate_key) as n_keys,
    countif(device_date is null) as null_device_date,
from `teamster-332318`.zz_cbini_kippnewark_amplify.stg_amplify__mclass__sftp__pm_student_summary
```

Expected: `n = n_keys`, `null_device_date = 0`.

- [ ] **Step 8: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-amplify-package-intermediates
git -C "$wt" add src/dbt/amplify/models/mclass/sftp/staging
git -C "$wt" commit -m "refactor(amplify): device_date fallback and a unique PM key in the package

Refs #5305

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: kipptaf API wrappers over the frozen archive

**Files:**

- Create:
  `src/dbt/kipptaf/models/amplify/mclass/api/staging/stg_amplify__mclass__api__benchmark_student_summary.sql`
- Create:
  `src/dbt/kipptaf/models/amplify/mclass/api/staging/stg_amplify__mclass__api__pm_student_summary.sql`
- Create:
  `src/dbt/kipptaf/models/amplify/mclass/api/staging/properties/stg_amplify__mclass__api__benchmark_student_summary.yml`
- Create:
  `src/dbt/kipptaf/models/amplify/mclass/api/staging/properties/stg_amplify__mclass__api__pm_student_summary.yml`

**Interfaces:**

- Consumes: source `amplify.stg_amplify__mclass__api__benchmark_student_summary`
  and `amplify.stg_amplify__mclass__api__pm_student_summary` from
  `src/dbt/kipptaf/models/amplify/mclass/sources-bigquery.yml` (unchanged).
- Produces: two views whose columns use SFTP names, so `union_relations` in Task
  3 aligns them with the SFTP wrappers without `coalesce`.

- [ ] **Step 1: Benchmark API wrapper SQL**

```sql
select
    * except (
        client_date,
        dibels_composite_score_lexile,
        official_teacher_name,
        official_teacher_staff_id,
        reading_comprehension_maze_discontinued,
        reading_comprehension_maze_level,
        reading_comprehension_maze_national_norm_percentile,
        reading_comprehension_maze_score,
        reading_comprehension_maze_semester_growth,
        reading_comprehension_maze_tested_out,
        reading_comprehension_maze_year_growth
    ),

    client_date as device_date,
    dibels_composite_score_lexile as composite_score_lexile,
    official_teacher_name as enrollment_teacher_name,
    official_teacher_staff_id as enrollment_teacher_staff_id,
    reading_comprehension_maze_discontinued as basic_comprehension_maze_discontinued,
    reading_comprehension_maze_level as basic_comprehension_maze_level,
    reading_comprehension_maze_national_norm_percentile
    as basic_comprehension_maze_national_norm_percentile,
    reading_comprehension_maze_score as basic_comprehension_maze_score,
    reading_comprehension_maze_semester_growth
    as basic_comprehension_maze_semester_growth,
    reading_comprehension_maze_tested_out as basic_comprehension_maze_tested_out,
    reading_comprehension_maze_year_growth as basic_comprehension_maze_year_growth,
from {{ source("amplify", "stg_amplify__mclass__api__benchmark_student_summary") }}
```

- [ ] **Step 2: PM API wrapper SQL**

```sql
select
    * except (
        account_name,
        client_date,
        official_teacher_name,
        official_teacher_staff_id,
        student_id_state_id,
        student_primary_id
    ) replace (coalesce(account_name, district_name) as district_name),

    client_date as device_date,
    official_teacher_name as enrollment_teacher_name,
    official_teacher_staff_id as enrollment_teacher_staff_id_teachernumber,
    student_id_state_id as secondary_student_id_stateid,
    student_primary_id as student_primary_id_studentnumber,
from {{ source("amplify", "stg_amplify__mclass__api__pm_student_summary") }}
```

- [ ] **Step 3: Benchmark API wrapper YAML**

```yaml
models:
  - name: stg_amplify__mclass__api__benchmark_student_summary
    description: >-
      Frozen Amplify mCLASS API benchmark archive (SY22-23 through SY24-25, New
      Jersey and Miami), with its API column names aliased to the SFTP file's
      names so it unions with the live feed without per-column coalesces. Read
      only through int_amplify__mclass__benchmark_student_summary.
    config:
      meta:
        contains_pii: true
    columns:
      - name: device_date
        data_type: date
        description: The archive's client_date under the SFTP name.
      - name: composite_score_lexile
        data_type: string
        description:
          The archive's dibels_composite_score_lexile under the SFTP name.
      - name: enrollment_teacher_name
        data_type: string
        description: The archive's official_teacher_name under the SFTP name.
      - name: enrollment_teacher_staff_id
        data_type: string
        description:
          The archive's official_teacher_staff_id under the SFTP name.
      - name: basic_comprehension_maze_score
        data_type: numeric
        description:
          The archive's reading_comprehension_maze_score under the SFTP name.
      - name: basic_comprehension_maze_level
        data_type: string
        description:
          The archive's reading_comprehension_maze_level under the SFTP name.
      - name: basic_comprehension_maze_national_norm_percentile
        data_type: numeric
        description: >-
          The archive's reading_comprehension_maze_national_norm_percentile
          under the SFTP name.
      - name: basic_comprehension_maze_semester_growth
        data_type: string
        description: >-
          The archive's reading_comprehension_maze_semester_growth under the
          SFTP name.
      - name: basic_comprehension_maze_year_growth
        data_type: string
        description:
          The archive's reading_comprehension_maze_year_growth under the SFTP
          name.
      - name: basic_comprehension_maze_tested_out
        data_type: boolean
        description:
          The archive's reading_comprehension_maze_tested_out under the SFTP
          name.
      - name: basic_comprehension_maze_discontinued
        data_type: boolean
        description: >-
          The archive's reading_comprehension_maze_discontinued under the SFTP
          name.
```

- [ ] **Step 4: PM API wrapper YAML**

```yaml
models:
  - name: stg_amplify__mclass__api__pm_student_summary
    description: >-
      Frozen Amplify mCLASS API progress monitoring archive (SY22-23 through
      SY24-25, New Jersey and Miami), with its API column names aliased to the
      SFTP file's names so it unions with the live feed without per-column
      coalesces. Read only through int_amplify__mclass__pm_student_summary.
    config:
      meta:
        contains_pii: true
    columns:
      - name: device_date
        data_type: date
        description: The archive's client_date under the SFTP name.
      - name: district_name
        data_type: string
        description:
          First non-null of the archive's account_name and district_name.
      - name: enrollment_teacher_name
        data_type: string
        description: The archive's official_teacher_name under the SFTP name.
      - name: enrollment_teacher_staff_id_teachernumber
        data_type: string
        description:
          The archive's official_teacher_staff_id under the SFTP name.
      - name: secondary_student_id_stateid
        data_type: string
        description: The archive's student_id_state_id under the SFTP name.
      - name: student_primary_id_studentnumber
        data_type: int64
        description: >-
          The archive's student_primary_id under the SFTP name. Raw vendor id;
          the Focus offset is applied downstream.
```

- [ ] **Step 5: Dry-run both wrappers' SQL against prod**

Use `dbt compile`, then dry-run the compiled SQL through the BigQuery MCP with
`dry_run: true`. The `except ... replace` combination on the PM wrapper is the
thing to prove.

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-amplify-package-intermediates
uv run dbt compile --select stg_amplify__mclass__api__benchmark_student_summary stg_amplify__mclass__api__pm_student_summary \
  --target prod --project-dir "$wt/src/dbt/kipptaf" --profiles-dir /workspaces/teamster/.dbt
```

Read each file under
`$wt/src/dbt/kipptaf/target/compiled/kipptaf/models/amplify/mclass/api/staging/`
and dry-run it. Expected: both dry runs return a schema, no error.

- [ ] **Step 6: Build both wrappers in dev**

```bash
uv run dbt build --select stg_amplify__mclass__api__benchmark_student_summary stg_amplify__mclass__api__pm_student_summary \
  --target dev --project-dir "$wt/src/dbt/kipptaf" --profiles-dir /workspaces/teamster/.dbt \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: 2 views created in `zz_cbini_kipptaf_amplify`.

- [ ] **Step 7: Commit**

```bash
git -C "$wt" add src/dbt/kipptaf/models/amplify/mclass/api
git -C "$wt" commit -m "refactor(amplify): wrap the frozen API archive under SFTP column names

Refs #5305

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Collapse the two mClass intermediates and simplify the PM SFTP wrapper

**Files:**

- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/sftp/staging/stg_amplify__mclass__sftp__pm_student_summary.sql`
- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/int_amplify__mclass__benchmark_student_summary.sql`
- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/int_amplify__mclass__pm_student_summary.sql`
- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/properties/int_amplify__mclass__benchmark_student_summary.yml`
- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/properties/int_amplify__mclass__pm_student_summary.yml`

**Interfaces:**

- Consumes: Task 2's wrappers; the package PM staging from Task 1 (through the
  `kippnewark_amplify` and `kipppaterson_amplify` sources).
- Produces: `int_amplify__mclass__benchmark_student_summary` with SFTP names:
  `device_date`, `composite_score_lexile`, `enrollment_teacher_name`,
  `enrollment_teacher_staff_id`, `basic_comprehension_maze_*` (8 columns
  including `_local_percentile`), `student_primary_id` (Focus-offset), `region`,
  `school`, `schoolid`, `_dbt_source_project`, `surrogate_key`.
  `int_amplify__mclass__pm_student_summary` with `device_date`,
  `enrollment_teacher_name`, `enrollment_teacher_staff_id_teachernumber`,
  `secondary_student_id_stateid`, `district_name`, `school_primary_id`,
  `student_primary_id` (Focus-offset), `matching_season`, `region`, `school`,
  `_dbt_source_project`, `surrogate_key`, `measure`, `pm_period`,
  `probe_number`, `assessment_grade`, `enrollment_grade`, `academic_year`,
  `measure_standard_score`, `measure_standard_score_change`, `sync_date`.

- [ ] **Step 1: PM SFTP wrapper becomes a plain union**

Replace `stg_amplify__mclass__sftp__pm_student_summary.sql` with:

```sql
{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_amplify", "stg_amplify__mclass__sftp__pm_student_summary"),
            source(
                "kipppaterson_amplify", "stg_amplify__mclass__sftp__pm_student_summary"
            ),
        ]
    )
}}
```

- [ ] **Step 2: Benchmark intermediate SQL**

Replace `int_amplify__mclass__benchmark_student_summary.sql` with:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_amplify__mclass__sftp__benchmark_student_summary"),
                    ref("stg_amplify__mclass__api__benchmark_student_summary"),
                ],
                source_column_name="_dbt_source_relation_2",
            )
        }}
    ),

    location_xref as (
        select
            ur.*,

            x.location_abbreviation as school,
            x.location_powerschool_school_id as schoolid,
            x.location_dagster_code_location as _dbt_source_project,

            initcap(
                regexp_extract(x.location_dagster_code_location, r'kipp(\w+)')
            ) as region,
        from union_relations as ur
        left join
            {{ ref("int_people__location_crosswalk") }} as x
            on ur.school_name = x.location_name
    )

select
    * except (student_primary_id),

    {{
        focus_student_number(
            "student_primary_id", "academic_year", "_dbt_source_project"
        )
    }} as student_primary_id,

from location_xref
```

- [ ] **Step 3: PM intermediate SQL**

Replace `int_amplify__mclass__pm_student_summary.sql` with:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_amplify__mclass__sftp__pm_student_summary"),
                    ref("stg_amplify__mclass__api__pm_student_summary"),
                ],
                source_column_name="_dbt_source_relation_2",
            )
        }}
    ),

    location_xref as (
        select
            ur.*,

            x.location_abbreviation as school,
            x.location_powerschool_school_id as schoolid,
            x.location_dagster_code_location as _dbt_source_project,

            initcap(
                regexp_extract(x.location_dagster_code_location, r'kipp(\w+)')
            ) as region,
        from union_relations as ur
        left join
            {{ ref("int_people__location_crosswalk") }} as x
            on ur.school_name = x.location_name
    )

select
    * except (
        schoolid, school_primary_id, primary_school_id, student_primary_id_studentnumber
    ),

    coalesce(schoolid, school_primary_id) as school_primary_id,

    {{
        focus_student_number(
            "student_primary_id_studentnumber", "academic_year", "_dbt_source_project"
        )
    }} as student_primary_id,

    if(pm_period = 'BOY->MOY', 'MOY', 'EOY') as matching_season,

from location_xref
```

- [ ] **Step 4: Benchmark intermediate YAML**

In `int_amplify__mclass__benchmark_student_summary.yml`:

Add a model-level `data_tests:` block between `config:` and `columns:`:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - student_primary_id
          - school_year
          - benchmark_period
          - assessment_grade
      config:
        severity: error
```

Rename these column entries (today at lines 591 to 647) and replace their "First
non-null of ..." descriptions:

| Today                                                 | Becomes                                             | Description                                                   |
| ----------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------- |
| `reading_comprehension_maze_local_percentile`         | `basic_comprehension_maze_local_percentile`         | Local percentile for the Maze measure. SFTP rows only.        |
| `official_teacher_staff_id`                           | `enrollment_teacher_staff_id`                       | Enrollment teacher staff id(s), pipe-delimited when multiple. |
| `official_teacher_name`                               | `enrollment_teacher_name`                           | Enrollment teacher name(s), pipe-delimited when multiple.     |
| `client_date`                                         | `device_date`                                       | Date the assessment was administered on the device.           |
| `dibels_composite_score_lexile`                       | `composite_score_lexile`                            | Lexile band for the composite score.                          |
| `reading_comprehension_maze_score`                    | `basic_comprehension_maze_score`                    | Maze score.                                                   |
| `reading_comprehension_maze_semester_growth`          | `basic_comprehension_maze_semester_growth`          | Maze semester growth classification.                          |
| `reading_comprehension_maze_year_growth`              | `basic_comprehension_maze_year_growth`              | Maze year growth classification.                              |
| `reading_comprehension_maze_national_norm_percentile` | `basic_comprehension_maze_national_norm_percentile` | Maze national norm percentile.                                |
| `reading_comprehension_maze_level`                    | `basic_comprehension_maze_level`                    | Maze benchmark level.                                         |
| `reading_comprehension_maze_tested_out`               | `basic_comprehension_maze_tested_out`               | Whether the student tested out of Maze.                       |
| `reading_comprehension_maze_discontinued`             | `basic_comprehension_maze_discontinued`             | Whether Maze was discontinued for the student.                |

Keep each entry's `data_type`. The `surrogate_key` description says "Hash of
student_primary_id, school_year, pm_period, measure, and probe_number", which is
wrong for this model; replace it with "Hash of the source's student number,
school_year, benchmark_period and assessment_grade, carried from staging."

- [ ] **Step 5: PM intermediate YAML**

In `int_amplify__mclass__pm_student_summary.yml`:

Add the model-level test block between `config:` and `columns:`:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - student_primary_id
          - school_year
          - pm_period
          - measure
          - probe_number
          - device_date
          - assessment_grade
      config:
        severity: error
```

Rename these entries and replace their descriptions:

| Today                       | Becomes                                     | Description                                                   |
| --------------------------- | ------------------------------------------- | ------------------------------------------------------------- |
| `student_id_state_id`       | `secondary_student_id_stateid`              | State student id.                                             |
| `official_teacher_staff_id` | `enrollment_teacher_staff_id_teachernumber` | Enrollment teacher staff id(s), pipe-delimited when multiple. |
| `official_teacher_name`     | `enrollment_teacher_name`                   | Enrollment teacher name(s), pipe-delimited when multiple.     |
| `client_date`               | `device_date`                               | Date the probe was administered on the device.                |

Replace the `surrogate_key` description with "Hash of the source's student
number, school_year, pm_period, measure, probe_number, device_date and
assessment_grade, carried from staging. Archive rows carry the archive's own
key."

- [ ] **Step 6: Build the wrapper and both intermediates in dev, tests
      included**

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-amplify-package-intermediates
uv run dbt build --select stg_amplify__mclass__sftp__pm_student_summary int_amplify__mclass__benchmark_student_summary int_amplify__mclass__pm_student_summary \
  --target dev --project-dir "$wt/src/dbt/kipptaf" --profiles-dir /workspaces/teamster/.dbt \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: 3 models build; both `unique_combination_of_columns` tests PASS; the
`relationships` test on the PM wrapper's `school_name` gives the same result as
prod (warn is acceptable there, it is not new).

Under `target=dev` the `kippnewark_amplify` and `kipppaterson_amplify` sources
resolve to `zz_cbini_<district>_amplify`, which Task 1 populated for the PM
model. The benchmark SFTP wrapper and the API wrappers are unmodified in this
task, so `--favor-state` points the benchmark wrapper at prod and the API
wrappers at the dev views built in Task 2. If the benchmark intermediate fails
`Not found: Table zz_cbini_kipptaf_amplify.stg_amplify__mclass__api__...`, Task
2 Step 6 did not build; rerun it.

- [ ] **Step 7: Commit**

```bash
git -C "$wt" add src/dbt/kipptaf/models/amplify/mclass
git -C "$wt" commit -m "refactor(amplify): union the archive wrappers, drop the coalesce pairs, add natural-key tests

Refs #5305

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Consumers inside `models/amplify/` read the SFTP names

**Files:**

- Modify:
  `src/dbt/kipptaf/models/amplify/mclass/intermediate/int_amplify__mclass__benchmark_student_summary_unpivot.sql:79-83`
- Modify:
  `src/dbt/kipptaf/models/amplify/intermediate/int_amplify__benchmark_student_summary.sql:15`
- Modify:
  `src/dbt/kipptaf/models/amplify/intermediate/int_amplify__all_assessments.sql:28,68`

**Interfaces:**

- Consumes: Task 3's renamed intermediate columns.
- Produces: unchanged output columns on all three models, so nothing outside
  `models/amplify/` moves.

- [ ] **Step 1: Unpivot**

In `int_amplify__mclass__benchmark_student_summary_unpivot.sql`, replace the
Maze tuple (lines 78 to 84):

```sql
                    (
                        basic_comprehension_maze_level,
                        basic_comprehension_maze_national_norm_percentile,
                        basic_comprehension_maze_score,
                        basic_comprehension_maze_semester_growth,
                        basic_comprehension_maze_year_growth
                    ) as 'Reading Comprehension (Maze)',
```

The label stays `'Reading Comprehension (Maze)'`; it is what the expectation
gate joins on.

- [ ] **Step 2: Benchmark summary**

In `int_amplify__benchmark_student_summary.sql` line 15, change

```sql
            bss.client_date,
```

to

```sql
            bss.device_date as client_date,
```

- [ ] **Step 3: All assessments, Internal branch**

In `int_amplify__all_assessments.sql`:

Line 28, change `p.client_date,` to `p.device_date as client_date,`.

Line 68, change `and p.client_date between e.start_date and e.end_date` to
`and p.device_date between e.start_date and e.end_date`.

The Aimline branch (lines 103 and 149) already reads `p.device_date`; leave it.

- [ ] **Step 4: Build the chain through the dashboard in dev**

`--favor-state` resolves every UNSELECTED model to prod, and prod still has the
API names, so the Task 3 models must be in `--select` or this build fails
`Name basic_comprehension_maze_level not found`. Select the whole chain:

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-amplify-package-intermediates
uv run dbt build --select stg_amplify__mclass__sftp__pm_student_summary int_amplify__mclass__benchmark_student_summary int_amplify__mclass__pm_student_summary int_amplify__mclass__benchmark_student_summary_unpivot int_amplify__benchmark_student_summary int_amplify__all_assessments int_amplify__pm_met_criteria int_amplify__pm_met_criteria_aimline int_students__dibels_participation_roster rpt_tableau__dibels_dashboard \
  --target dev --project-dir "$wt/src/dbt/kipptaf" --profiles-dir /workspaces/teamster/.dbt \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: every model builds; every `severity: error` test passes; warn-level
results match what prod reports today (compare against the latest prod run in
Dagster if any warns appear).

Use this full selection for Task 5 as well; a narrower re-run invalidates the
comparison.

- [ ] **Step 5: Commit**

```bash
git -C "$wt" add src/dbt/kipptaf/models/amplify
git -C "$wt" commit -m "refactor(amplify): read the SFTP column names in the unpivot and assessment models

Refs #5305

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Verify against prod

**Files:** none edited. Results go in the PR body (Task 7) as counts only.

- [ ] **Step 1: Row count and distinct natural key, four models**

Via the BigQuery MCP. Prod schemas: `kipptaf_amplify`, `kipptaf_students`,
`kipptaf_tableau`. Dev schemas: the same with the `zz_cbini_` prefix. Confirm
dev schema names first:

```sql
select schema_name
from `teamster-332318`.INFORMATION_SCHEMA.SCHEMATA
where schema_name like 'zz_cbini_kipptaf_%'
```

Then:

```sql
select 'prod' as side, 'bm_int' as model, count(*) as n,
    count(distinct format('%T|%T|%T|%T', student_primary_id, school_year, benchmark_period, assessment_grade)) as n_keys
from `teamster-332318`.kipptaf_amplify.int_amplify__mclass__benchmark_student_summary
union all
select 'dev', 'bm_int', count(*),
    count(distinct format('%T|%T|%T|%T', student_primary_id, school_year, benchmark_period, assessment_grade))
from `teamster-332318`.zz_cbini_kipptaf_amplify.int_amplify__mclass__benchmark_student_summary
union all
select 'prod', 'pm_int', count(*),
    count(distinct format('%T|%T|%T|%T|%T|%T|%T', student_primary_id, school_year, pm_period, measure, probe_number, client_date, assessment_grade))
from `teamster-332318`.kipptaf_amplify.int_amplify__mclass__pm_student_summary
union all
select 'dev', 'pm_int', count(*),
    count(distinct format('%T|%T|%T|%T|%T|%T|%T', student_primary_id, school_year, pm_period, measure, probe_number, device_date, assessment_grade))
from `teamster-332318`.zz_cbini_kipptaf_amplify.int_amplify__mclass__pm_student_summary
union all
select 'prod', 'all_assessments', count(*),
    count(distinct format('%T|%T|%T|%T|%T|%T|%T|%T', academic_year, student_number, model_type, period, round_number, assessment_grade_int, measure_standard, client_date))
from `teamster-332318`.kipptaf_amplify.int_amplify__all_assessments
union all
select 'dev', 'all_assessments', count(*),
    count(distinct format('%T|%T|%T|%T|%T|%T|%T|%T', academic_year, student_number, model_type, period, round_number, assessment_grade_int, measure_standard, client_date))
from `teamster-332318`.zz_cbini_kipptaf_amplify.int_amplify__all_assessments
union all
select 'prod', 'dashboard', count(*), null
from `teamster-332318`.kipptaf_tableau.rpt_tableau__dibels_dashboard
union all
select 'dev', 'dashboard', count(*), null
from `teamster-332318`.zz_cbini_kipptaf_tableau.rpt_tableau__dibels_dashboard
order by model, side
```

Expected: `n` and `n_keys` equal between prod and dev for each model. If the
live SFTP file was re-pulled between the prod build and yours, the SFTP-side
rows can differ by the day's delta; confirm by comparing
`max(_dagster_partition_key)` or `max(sync_date)` on both sides before reading a
delta as a regression.

- [ ] **Step 2: Column-by-column diff on the benchmark intermediate**

```sql
select
    count(*) as matched,
    countif(p.reading_comprehension_maze_score is distinct from d.basic_comprehension_maze_score) as maze_score,
    countif(p.reading_comprehension_maze_level is distinct from d.basic_comprehension_maze_level) as maze_level,
    countif(p.reading_comprehension_maze_national_norm_percentile is distinct from d.basic_comprehension_maze_national_norm_percentile) as maze_pct,
    countif(p.reading_comprehension_maze_semester_growth is distinct from d.basic_comprehension_maze_semester_growth) as maze_sem,
    countif(p.reading_comprehension_maze_year_growth is distinct from d.basic_comprehension_maze_year_growth) as maze_year,
    countif(p.reading_comprehension_maze_tested_out is distinct from d.basic_comprehension_maze_tested_out) as maze_tested_out,
    countif(p.reading_comprehension_maze_discontinued is distinct from d.basic_comprehension_maze_discontinued) as maze_disc,
    countif(p.reading_comprehension_maze_local_percentile is distinct from d.basic_comprehension_maze_local_percentile) as maze_local,
    countif(p.dibels_composite_score_lexile is distinct from d.composite_score_lexile) as lexile,
    countif(p.official_teacher_name is distinct from d.enrollment_teacher_name) as teacher_name,
    countif(p.official_teacher_staff_id is distinct from d.enrollment_teacher_staff_id) as teacher_id,
    countif(p.client_date is distinct from d.device_date) as client_date,
    countif(p.composite_score is distinct from d.composite_score) as composite_score,
    countif(p.composite_level is distinct from d.composite_level) as composite_level,
    countif(p.region is distinct from d.region) as region,
    countif(p.school is distinct from d.school) as school,
    countif(p.schoolid is distinct from d.schoolid) as schoolid,
    countif(p._dbt_source_project is distinct from d._dbt_source_project) as source_project,
    countif(p.surrogate_key is distinct from d.surrogate_key) as surrogate_key,
from `teamster-332318`.kipptaf_amplify.int_amplify__mclass__benchmark_student_summary as p
inner join `teamster-332318`.zz_cbini_kipptaf_amplify.int_amplify__mclass__benchmark_student_summary as d
    on p.student_primary_id = d.student_primary_id
    and p.school_year = d.school_year
    and p.benchmark_period = d.benchmark_period
    and p.assessment_grade = d.assessment_grade
```

Expected: `matched` equals the prod row count from Step 1; every other column
is 0.

- [ ] **Step 3: Column-by-column diff on the PM intermediate**

```sql
select
    count(*) as matched,
    countif(p.official_teacher_name is distinct from d.enrollment_teacher_name) as teacher_name,
    countif(p.official_teacher_staff_id is distinct from d.enrollment_teacher_staff_id_teachernumber) as teacher_id,
    countif(p.student_id_state_id is distinct from d.secondary_student_id_stateid) as state_id,
    countif(p.district_name is distinct from d.district_name) as district_name,
    countif(p.school_primary_id is distinct from d.school_primary_id) as school_primary_id,
    countif(p.measure_standard_score is distinct from d.measure_standard_score) as score,
    countif(p.measure_name_code is distinct from d.measure_name_code) as code,
    countif(p.matching_season is distinct from d.matching_season) as matching_season,
    countif(p.region is distinct from d.region) as region,
    countif(p.school is distinct from d.school) as school,
    countif(p._dbt_source_project is distinct from d._dbt_source_project) as source_project,
    countif(p.surrogate_key is distinct from d.surrogate_key) as surrogate_key,
from `teamster-332318`.kipptaf_amplify.int_amplify__mclass__pm_student_summary as p
inner join `teamster-332318`.zz_cbini_kipptaf_amplify.int_amplify__mclass__pm_student_summary as d
    on p.student_primary_id = d.student_primary_id
    and p.school_year = d.school_year
    and p.pm_period = d.pm_period
    and p.measure = d.measure
    and p.probe_number = d.probe_number
    and p.client_date = d.device_date
    and p.assessment_grade = d.assessment_grade
```

Expected: `matched` equals the prod row count; every column 0 EXCEPT
`surrogate_key`, which differs on every SFTP row (the widened key) and is 0 on
archive rows. Record the `surrogate_key` count; it should equal the SFTP share
of the model.

- [ ] **Step 4: Dashboard grain unchanged**

```sql
select side, count(*) as n, count(distinct format('%T|%T|%T|%T|%T|%T|%T', academic_year, student_number, model_type, assessment_type, period, round_number, measure_standard)) as n_keys
from (
    select 'prod' as side, * from `teamster-332318`.kipptaf_tableau.rpt_tableau__dibels_dashboard
    union all
    select 'dev', * from `teamster-332318`.zz_cbini_kipptaf_tableau.rpt_tableau__dibels_dashboard
)
group by side
```

Expected: identical `n` and `n_keys`. If the column lists differ between prod
and dev (the `union all` errors), fall back to per-side counts; a column
difference here means a consumer outside `models/amplify/` changed and the plan
has a gap.

---

### Task 6: Docs

**Files:**

- Modify: `src/dbt/amplify/CLAUDE.md`
- Modify: `.claude/skills/dibels-dashboard/SKILL.md:1456-1464`

- [ ] **Step 1: Rewrite the package CLAUDE.md**

Replace `src/dbt/amplify/CLAUDE.md` with:

```markdown
# CLAUDE.md — `dbt/amplify/`

Source-system staging project for **Amplify** reading assessments. Covers two
product lines with different ingestion paths, split into method subfolders:

- `dds/` — Amplify DDS (SFTP file drops)
- `mclass/api/` — mClass API data
- `mclass/sftp/` — mClass SFTP file drops

`dds` and `mclass/api` can be independently enabled/disabled per school in the
consuming project's `dbt_project.yml` (e.g. `kipppaterson` disables both).

## One network account, landing in Newark's bucket

Amplify exports one account for the whole network, and the mClass SFTP files
land in `kippnewark`'s bucket. The `kippnewark` copies of the `mclass/sftp`
staging models therefore carry Camden, Miami and Paterson schools too, and
`_dbt_source_relation` on a kipptaf union over them is NOT region. Region is
resolved in kipptaf from `int_people__location_crosswalk` on `school_name`.
`kipppaterson` has its own file through AY2025 only; kipptaf carries natural-key
uniqueness tests on its mClass intermediates so a resumed Paterson feed fails
instead of doubling.

## What lives here versus kipptaf

Here: casts, measure-name normalization, the `device_date` fallback to
`sync_date`, and a surrogate key that is unique per row. Nothing that needs
another source.

kipptaf (`models/amplify/`): `select *` union wrappers over the two districts,
two `stg_amplify__mclass__api__*` wrappers that alias the frozen SY22-25 API
archive to this package's SFTP column names, the crosswalk join, the Miami Focus
student-number offset, the benchmark unpivot, and the base-plus-aimline PM
combine. The last two stay in kipptaf because the archive needs the unpivot too
and the aimline combine only works after the union.

A column ADD or rename on a contracted staging model here needs the two-PR
pattern or `zz_stg_` seeding for Newark and Paterson
(`.claude/rules/dbt-models.md`). A value-only change does not.
```

- [ ] **Step 2: Update the DIBELS skill paragraph**

In `.claude/skills/dibels-dashboard/SKILL.md`, replace the paragraph starting
`It deduped PM at all only by accident:` (lines 1456 to 1464) with:

```markdown
It deduped PM at all only by accident:
`int_amplify__mclass__pm_student_summary`'s surrogate key used to omit
`probe_number` and `device_date`, so it collided across a student's probes --
67,984 AY2025 rows against 33,917 distinct keys. **Fixed in #5305**: the key now
covers student, school year, PM period, measure, probe, device date and
assessment grade, and the model carries a severity-error natural-key test. The
diagnostic lesson still stands: `count(distinct surrogate_key) < count(*)` on a
model whose key you have not read is not proof of fan-out -- using it that way
mis-read 1,352 genuine multi-probe rounds as gate duplication during this
session.
```

- [ ] **Step 3: Lint both files**

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-amplify-package-intermediates
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/amplify/CLAUDE.md .claude/skills/dibels-dashboard/SKILL.md </dev/null
```

Expected: no issues, or formatting-only findings the commit hook fixes.

- [ ] **Step 4: Commit**

```bash
git -C "$wt" add src/dbt/amplify/CLAUDE.md .claude/skills/dibels-dashboard/SKILL.md
git -C "$wt" commit -m "docs(amplify): one network account in Newark's bucket; PM key is unique now

Refs #5305

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Lint, push, open the PR

**Files:** none edited beyond lint fixes.

- [ ] **Step 1: Lint every changed SQL and YAML file**

```bash
wt=/workspaces/teamster/.worktrees/cbini/refactor/claude-amplify-package-intermediates
cd "$wt" && files=$(git diff --name-only origin/main...HEAD -- '*.sql' '*.yml' '*.md' | while read -r f; do [ -f "$f" ] && echo "$f"; done) && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix $files </dev/null
```

Expected: `No issues`. Run it in the background if it exceeds 2 minutes and read
the output only after it exits. Fix any finding (sqlfluff ST06 ordering, CV03
trailing commas, MD060 table padding) and amend the relevant task's commit or
add a `style:` commit.

- [ ] **Step 2: Push**

```bash
git -C "$wt" push
```

Expected: the pre-push hook passes and the branch updates on
`origin/cbini/refactor/claude-amplify-package-intermediates`.

- [ ] **Step 3: Open the PR**

Read `.github/pull_request_template.md` in the worktree and fill it. Title:
`refactor(amplify): move the Amplify-only value logic into the package and alias the frozen archive at kipptaf`.
Body includes `Closes #5305`, the Task 5 counts (numbers only, no student
values), the note that the PM `surrogate_key` hash changes on SFTP rows, and
ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
Create it with `mcp__github__create_pull_request` against `main`. Do not
hard-wrap the body.

- [ ] **Step 4: Watch CI**

Invoke `pr-ci-review`. The dbt Cloud CI job builds `state:modified+` for kipptaf
only; the package change is exercised through the PM SFTP wrapper, which CI
rebuilds from the district `zz_stg` copies. A CI failure naming
`Name basic_comprehension_maze_level not found` means a stale per-PR shadow of
an intermediate; follow the kipptaf CLAUDE.md "stale per-PR shadow" note.
Process `claude-review` findings through `superpowers:receiving-code-review`.
