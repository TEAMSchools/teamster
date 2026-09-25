# Cambium EOC Score File Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest the Cambium EOC (Algebra I, Algebra II, Geometry) score file
for Newark and Camden into `int_pearson__all_assessments` with the Pearson-era
row shape, and carry the student's grade-when-assessed through to kipptaf.

**Architecture:** A new `eoc` SFTP asset per region lands the file under
`cambium/eoc/`. A new `src_cambium__eoc` external is unioned into the existing
`stg_cambium__njsla` behind a `cambium_eoc_enabled` var (Paterson turns it off).
EOC rows get `discipline = 'Math'` and NULL `test_grade` / `assessmentgrade`; a
renamed `gradelevelwhenassessed` column flows through both union layers.

**Tech Stack:** Dagster (`build_sftp_file_asset`, Couchdrop sensor), dbt
BigQuery (`dbt_utils.union_relations`, dbt-external-tables), pytest.

**Spec:** `docs/superpowers/specs/2026-09-22-cambium-eoc-ingest-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest`
  (abbreviated `$WT` below — type the full path; never expand an uppercase shell
  variable, the hook denies it). Every git call is `git -C <worktree>`.
- Always `uv run` for python, dbt, pytest. Run
  `uv run dbt deps --project-dir <project>` once per project before its first
  dbt command, in its own Bash call.
- EOC subjects, verbatim: `Algebra I`, `Algebra II`, `Geometry`. EOC test codes:
  `ALG01`, `ALG02`, `GEO01`.
- EOC filename suffix: `_SLA_EOC`. Folder:
  `/data-team/<code_location>/cambium/eoc`.
- EOC rows: `test_grade` NULL, `assessmentgrade` NULL, `discipline = 'Math'`.
- New column name is `gradelevelwhenassessed` (int64) everywhere downstream of
  the cambium staging models.
- Staging tests set `config: severity: error` on every test.
- No PII values in commits, PR bodies, or comments. Row counts are fine.
- Commit messages go in files under the session scratchpad and commit with
  `git commit -F`; end each with
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Before pushing SQL/YAML/markdown run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.

## Review Focus

1. **Paterson with the var off.** A district without an EOC file must parse and
   compile `stg_cambium__njsla` with only the NJSLA source. Pinned in Task 2
   Steps 7 and 8.
2. **One feed's asset picking up another feed's file.** The `njsla` asset must
   never match a `_SLA_EOC` file in `/eoc`, and the `eoc` asset never a file in
   `/njsla` or `/njgpa`. Pinned in Task 1 by the cross-feed test with `_SLA_EOC`
   added to its tail list.
3. **A future EOC subject spelling Cambium has not sent** (e.g. `Algebra 1`). It
   must fail the build, not fall through to `ELA`. Pinned by the `subject`
   `accepted_values` test in Task 2.
4. **The same test in both files.** A row repeated across the NJSLA and EOC
   files must fail, not double-count. Pinned by the existing `studenttestuuid`
   `unique` test, which spans the union; Task 4 Step 5 runs it on real data.
5. **The first prod tick after merge.** The new external is excluded from the
   deps gate, so `stage_external_sources` runs against an empty prod prefix
   unless the `eoc` asset has landed. Task 5 launches the prod assets
   immediately after the deploy.

---

### Task 1: Dagster `eoc` assets and sensor wiring

**Files:**

- Modify: `src/teamster/code_locations/kippnewark/cambium/assets.py`
- Modify: `src/teamster/code_locations/kippcamden/cambium/assets.py`
- Modify: `src/teamster/code_locations/kippnewark/couchdrop/sensors.py`
- Modify: `src/teamster/code_locations/kippcamden/couchdrop/sensors.py`
- Test: `tests/libraries/test_cambium_assets.py`

**Interfaces:**

- Produces: asset `eoc` in each region's `cambium/assets.py`, key
  `[<code_location>, "cambium", "eoc"]`. Task 2's source asset key must match.

- [ ] **Step 1: Extend the test lists (failing test)**

In `tests/libraries/test_cambium_assets.py`, change the imports and lists at the
top:

```python
from teamster.code_locations.kippcamden.cambium.assets import eoc as camden_eoc
from teamster.code_locations.kippcamden.cambium.assets import njgpa as camden_njgpa
from teamster.code_locations.kippcamden.cambium.assets import njsla as camden_njsla
from teamster.code_locations.kippnewark.cambium.assets import eoc as newark_eoc
from teamster.code_locations.kippnewark.cambium.assets import njgpa as newark_njgpa
from teamster.code_locations.kippnewark.cambium.assets import njsla as newark_njsla
from teamster.libraries.cambium.assets import build_remote_file_regex

# The tail after `Record_File`, verified against the real Cambium files.
NJGPA_TAILS = ["_GPA"]
NJSLA_TAILS = ["_SLA"]
EOC_TAILS = ["_SLA_EOC"]

# district code embedded in each region's filename
ASSETS = [
    (newark_njgpa, "7325", NJGPA_TAILS),
    (newark_njsla, "7325", NJSLA_TAILS),
    (newark_eoc, "7325", EOC_TAILS),
    (camden_njgpa, "1799", NJGPA_TAILS),
    (camden_njsla, "1799", NJSLA_TAILS),
    (camden_eoc, "1799", EOC_TAILS),
]

# Every ordered pair of feeds within one region. Only the directory segment
# keeps one feed's asset off another feed's file.
REGIONS = [
    ([newark_njgpa, newark_njsla, newark_eoc], "7325"),
    ([camden_njgpa, camden_njsla, camden_eoc], "1799"),
]
```

In `test_one_feeds_asset_never_matches_another_feeds_file`, change the tail list
so the `njsla` asset is checked against a real EOC filename:

```python
    for tail in ["", "_GPA", "_SLA", "_SLA_EOC", "_ELA", "_MAT", "_SCI"]:
```

- [ ] **Step 2: Run the test to verify it fails**

Run (cwd = worktree):
`cd /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest && uv run pytest tests/libraries/test_cambium_assets.py -q 2>&1 | tail -n 5`
Expected: collection error, `ImportError: cannot import name 'eoc'`.

- [ ] **Step 3: Add the asset in both regions**

In `src/teamster/code_locations/kippnewark/cambium/assets.py` and the Camden
twin (identical text; each file's `DISTRICT_CODE` already differs), add after
the `njsla` definition:

```python
eoc = build_sftp_file_asset(
    asset_key=[*key_prefix, "eoc"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/eoc",
    remote_file_regex=build_remote_file_regex(
        partitions_def=partitions_def,
        district_code=DISTRICT_CODE,
        filename_suffix_regex=r"_SLA_EOC",
    ),
    # Cambium ships EOC with a byte-identical header to the NJSLA file.
    avro_schema=NJSLA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=partitions_def,
)
```

and change the list to:

```python
assets = [
    njgpa,
    njsla,
    eoc,
]
```

- [ ] **Step 4: Wire both sensors**

In `src/teamster/code_locations/kippnewark/couchdrop/sensors.py` and the Camden
twin, add the import beside the other cambium imports:

```python
from teamster.code_locations.kippnewark.cambium.assets import eoc as cambium_eoc
```

(Camden:
`from teamster.code_locations.kippcamden.cambium.assets import eoc as cambium_eoc`.)

and add `cambium_eoc,` as the first entry of `asset_selection`, before
`cambium_njgpa,`.

- [ ] **Step 5: Run the tests to verify they pass**

Run:
`cd /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest && uv run pytest tests/libraries/test_cambium_assets.py tests/libraries/test_cambium_schema.py -q 2>&1 | tail -n 5`
Expected: all pass.

- [ ] **Step 6: Validate both code locations load**

Write `tests/code_locations/test_zz_eoc_defs.py` (throwaway; the conftest loads
secrets):

```python
from dagster import AssetKey


def test_eoc_in_both_definitions():
    from teamster.code_locations.kippcamden.definitions import (
        defs as camden_defs,
    )
    from teamster.code_locations.kippnewark.definitions import (
        defs as newark_defs,
    )

    for defs, loc in [(newark_defs, "kippnewark"), (camden_defs, "kippcamden")]:
        assert defs.resolve_assets_def(AssetKey([loc, "cambium", "eoc"]))
        sensor = defs.resolve_sensor_def(f"{loc}__couchdrop__sftp_asset_sensor")
        assert sensor is not None
```

First confirm the sensor name:
`rg -n "name=" src/teamster/libraries/couchdrop/sensors.py | head -3`, and
adjust the string if it differs. Run:
`uv run pytest tests/code_locations/test_zz_eoc_defs.py -q 2>&1 | tail -n 5`.
Expected: PASS. If `definitions` fails to import on a missing dbt manifest,
record that and rely on Step 5 plus the branch deployment in Task 4. Delete the
file afterwards: `rm tests/code_locations/test_zz_eoc_defs.py`.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest commit -F <scratchpad>/commit-msg-eoc-assets.txt
```

Message: `feat(cambium): add EOC score file asset for Newark and Camden` +
`Refs #5481` + trailer.

---

### Task 2: cambium package — EOC source, union, EOC derivations, rename

**Files:**

- Modify: `src/dbt/cambium/models/sources-external.yml`
- Modify: `src/dbt/cambium/models/staging/stg_cambium__njsla.sql`
- Modify: `src/dbt/cambium/models/staging/properties/stg_cambium__njsla.yml`
- Modify: `src/dbt/cambium/models/staging/stg_cambium__njgpa.sql`
- Modify: `src/dbt/cambium/models/staging/properties/stg_cambium__njgpa.yml`
- Modify: `src/dbt/kipppaterson/dbt_project.yml`

**Interfaces:**

- Consumes: Dagster asset key `[<project>, cambium, eoc]` (Task 1).
- Produces: `stg_cambium__njsla` and `stg_cambium__njgpa` expose
  `gradelevelwhenassessed int64` in place of `grade_level_when_assessed`. Task 3
  lists that name.

- [ ] **Step 1: Add the source**

Append to `src/dbt/cambium/models/sources-external.yml` under `tables:`, after
`src_cambium__njsla`:

```yaml
- name: src_cambium__eoc
  config:
    meta:
      dagster:
        asset_key:
          - "{{ project_name }}"
          - cambium
          - eoc
  external:
    location:
      "{{ var('cloud_storage_uri_base',
      env_var('DBT_DEV_CLOUD_STORAGE_URI_BASE', '')) }}/cambium/eoc/*"
    options:
      connection_name: "{{ var('bigquery_external_connection_name') }}"
      metadata_cache_mode: MANUAL
      max_staleness: INTERVAL 7 DAY
      format: AVRO
      enable_logical_types: true
      hive_partition_uri_prefix:
        "{{ var('cloud_storage_uri_base',
        env_var('DBT_DEV_CLOUD_STORAGE_URI_BASE', '')) }}/cambium/eoc/"
```

- [ ] **Step 2: Union the sources in `stg_cambium__njsla.sql`**

Replace the opening `with` and the `njsla` CTE's `from` line. The file becomes:

```sql
{#- source() inside the branch is captured at parse time, so a district with
    cambium_eoc_enabled off never takes a dependency on src_cambium__eoc. -#}
{%- set relations = [source("cambium", "src_cambium__njsla")] -%}
{%- if var("cambium_eoc_enabled", true) -%}
    {%- do relations.append(source("cambium", "src_cambium__eoc")) -%}
{%- endif -%}

with
    union_relations as (
        {{ dbt_utils.union_relations(relations=relations) }}
    ),

    njsla as (
        select
            ...
        from union_relations
        where summative_flag = 'Y' and test_attemptedness_flag = 'Y'
    ),
```

(`...` is the existing column list, edited in Step 3; nothing else in the CTE
changes.)

- [ ] **Step 3: Null the EOC grade in the `njsla` CTE**

Remove `assessment_grade,` from the plain column list (line 6). Add this after
the `cast(test_score_complete as numeric) as test_score_complete,` line:

```sql
            /* EOC forms have no grade. Cambium stamps 'Grade 11' on every EOC
               row; Pearson sent NULL, which dim_assessments keys on. */
            if(
                `subject` in ('Algebra I', 'Algebra II', 'Geometry'),
                null,
                assessment_grade
            ) as assessment_grade,
```

`test_grade` in `aligned` then derives NULL through the existing
`regexp_extract`; do not touch it. If `trunk check` reports ST06 on this column,
move it to the position sqlfluff asks for within the same CTE.

- [ ] **Step 4: Map EOC subjects to Math and rename the grade column**

In the `leveled` CTE replace the `discipline` case with:

```sql
            case
                when
                    `subject`
                    in ('Mathematics', 'Algebra I', 'Algebra II', 'Geometry')
                then 'Math'
                when `subject` = 'Science'
                then 'Science'
                else 'ELA'
            end as discipline,
```

In the `aligned` CTE remove the plain `grade_level_when_assessed,` line and add
`grade_level_when_assessed as gradelevelwhenassessed,` in the renamed-alias
group, after `assessment_year as assessmentyear,`.

In `stg_cambium__njgpa.sql` `aligned` CTE, do the same: remove
`grade_level_when_assessed,` and add
`grade_level_when_assessed as gradelevelwhenassessed,` after
`assessment_grade as assessmentgrade,`.

- [ ] **Step 5: Update the properties files**

`stg_cambium__njsla.yml`:

- Model `description`: replace the sentence starting "Cambium ships English
  Language Arts" with: "Cambium ships English Language Arts, Mathematics and
  Science in the District Summative Record File, and the Algebra I, Algebra II
  and Geometry end-of-course tests in a separate EOC file with an identical
  header. This model unions both files, carries the NJSLA and the NJSLA Science
  assessments, and branches every subject-dependent column on subject."
- `test_grade`: replace `description` and the `not_null` test with:

```yaml
- name: test_grade
  data_type: int64
  description: >-
    Grade number parsed out of assessment_grade, which Cambium sends as 'Grade
    3' through 'Grade 11'. NULL for the Algebra I, Algebra II and Geometry
    end-of-course tests, whose forms have no grade, matching the Pearson rows.
    An unparseable value on any other row yields NULL and fails here rather than
    flowing a NULL grade into dim_assessments.
  data_tests:
    - not_null:
        config:
          severity: error
          where: "`subject` not in ('Algebra I', 'Algebra II', 'Geometry')"
```

(keep the existing `accepted_values` block unchanged).

- `subject`: description becomes "'English Language Arts', 'Mathematics',
  'Science', or one of the end-of-course subjects 'Algebra I', 'Algebra II' and
  'Geometry'. Drives every subject-dependent derivation in this model, so an
  unrecognized subject fails here rather than silently landing on the ELA
  branch." and `accepted_values` `values` becomes
  `[English Language Arts, Mathematics, Science, Algebra I, Algebra II, Geometry]`.
- `discipline`: description becomes
  `"'Math' for Mathematics and the end-of-course subjects, 'Science' for Science, else 'ELA'."`
- `assessmentgrade`: description becomes "The test DESIGN level as Cambium sends
  it, e.g. 'Grade 5'. NULL for end-of-course tests, whose 'Grade 11' is a
  placeholder. test_grade is the parsed integer; gradelevelwhenassessed is the
  student's own grade."
- Rename the column entry `grade_level_when_assessed` to
  `gradelevelwhenassessed`; description: "The student's grade at the time of
  testing. Equals test_grade on every grade-level test; on end-of-course tests,
  where test_grade is NULL, it is the only grade."
- `testcode` description: append "; ALG01, ALG02 and GEO01 for the end-of-course
  tests".

`stg_cambium__njgpa.yml`: rename `grade_level_when_assessed` to
`gradelevelwhenassessed` (keep its description), and in `assessmentgrade`'s
description replace `grade_level_when_assessed` with `gradelevelwhenassessed`.

Then sweep for stale references:
`rg -n "grade_level_when_assessed" src/dbt --glob '*.{sql,yml,md}' --glob '!**/target/**' --glob '!**/dbt_packages/**'`
Expected: only the two `cast(grade_level_when_assessed as int)` lines and the
two `grade_level_when_assessed as gradelevelwhenassessed` aliases.

- [ ] **Step 6: Paterson — turn the var off and disable the source**

In `src/dbt/kipppaterson/dbt_project.yml` `vars:` add, after
`edplan_has_archive: false`:

```yaml
# Paterson has no EOC file yet. Removing this and the src_cambium__eoc
# disable below is the dbt half of onboarding it.
cambium_eoc_enabled: false
```

and under `sources: cambium: cambium:` add beside `src_cambium__njgpa`:

```yaml
src_cambium__eoc:
  +enabled: false
```

- [ ] **Step 7: Parse every consumer**

One Bash call per project for deps first, then:

```bash
uv run dbt parse --no-partial-parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest/src/dbt/kippnewark 2>&1 | tail -n 5
uv run dbt parse --no-partial-parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest/src/dbt/kippcamden 2>&1 | tail -n 5
uv run dbt parse --no-partial-parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest/src/dbt/kipppaterson 2>&1 | tail -n 5
```

Expected: all three parse clean. Then confirm the graph edges:

```bash
uv run dbt ls --select +stg_cambium__njsla --resource-type source --project-dir <each project> 2>&1 | tail -n 5
```

Expected: Newark and Camden list `source:cambium.cambium.src_cambium__njsla` and
`src_cambium__eoc`; Paterson lists only `src_cambium__njsla`.

- [ ] **Step 8: Compile Paterson against staging**

`uv run dbt compile --select stg_cambium__njsla --target staging --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest/src/dbt/kipppaterson 2>&1 | tail -n 5`

This is not a warehouse write. Expected: success. Open the compiled SQL under
`target/compiled/cambium/models/staging/stg_cambium__njsla.sql` and confirm the
`union_relations` CTE selects from one relation only. (Newark and Camden cannot
compile until `src_cambium__eoc` is staged in Task 4.)

- [ ] **Step 9: Lint and commit**

`trunk check --force --no-fix` on the five cambium files and Paterson's
`dbt_project.yml`; fix any findings. Commit with message
`feat(cambium): union EOC scores into stg_cambium__njsla` + `Refs #5481` +
trailer.

---

### Task 3: Carry `gradelevelwhenassessed` through both unions

**Files:**

- Modify: `src/dbt/pearson/models/intermediate/int_pearson__all_assessments.sql`
- Modify:
  `src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql`
- Modify:
  `src/dbt/kipptaf/models/pearson/intermediate/properties/int_pearson__all_assessments.yml`

**Interfaces:**

- Consumes: `gradelevelwhenassessed int64` from Task 2 (cambium) and from
  `stg_pearson__njsla` / `_njsla_science` / `_parcc` (already present).
- Produces: `gradelevelwhenassessed` on kipptaf `int_pearson__all_assessments`.

- [ ] **Step 1: Add the include entries**

In both `int_pearson__all_assessments.sql` files, add
`"gradelevelwhenassessed",` to the `include=[...]` list in alphabetical position
(after `"firstname",` in both lists).

- [ ] **Step 2: Document the column in kipptaf**

In the kipptaf properties file, add after the `firstname` entry (blank line
between entries, as the file does):

```yaml
- name: gradelevelwhenassessed
  data_type: int64
  description: >-
    The student's grade at the time of testing. Equals test_grade on grade-level
    tests. On the Algebra I, Algebra II and Geometry end-of-course tests, where
    test_grade is NULL, it is the only grade. NULL for NJGPA rows from Pearson,
    which did not send it.
```

The pearson package's properties file documents only derived columns, so it gets
no entry.

- [ ] **Step 3: Parse and compile**

```bash
uv run dbt parse --no-partial-parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest/src/dbt/kippnewark 2>&1 | tail -n 3
uv run dbt parse --no-partial-parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest/src/dbt/kipptaf 2>&1 | tail -n 3
uv run dbt compile --select int_pearson__all_assessments --target staging --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest/src/dbt/kipptaf 2>&1 | tail -n 3
```

Expected: clean. In the kipptaf compiled SQL, `gradelevelwhenassessed` appears
in every branch — real in the cambium branches once they rebuild, otherwise
`cast(null as INT64) as gradelevelwhenassessed`. Confirm with
`grep -c gradelevelwhenassessed <compiled file>` being at least 8.

- [ ] **Step 4: Lint and commit**

`trunk check --force --no-fix` on the three files. Commit with
`feat(pearson): carry gradelevelwhenassessed through the NJ assessment unions` +
`Refs #5481` + trailer.

---

### Task 4: Open the PR and verify end to end in the branch deployment

**Files:** none changed unless a check fails.

- [ ] **Step 1: Push and open the PR non-draft**

`git -C <worktree> push`. Open the PR with `mcp__github__create_pull_request`
from `.github/pull_request_template.md`; body includes `Closes #5481`, the
`test_grade` decision, the post-merge prod launch step, and ends with
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Non-draft, so
the Dagster branch deployment builds.

- [ ] **Step 2: Materialize the branch-deployment assets**

Find the branch deployment with `mcp__dagster-plus__list_deployments`. Launch
`kippnewark/cambium/eoc` and `kippcamden/cambium/eoc`, partition `2026|Spring`,
with `mcp__dagster-plus__launch_asset_run` against that deployment. Confirm
success with `get_run`. The IO manager writes to
`gs://teamster-test/dagster/<project>/cambium/eoc/`.

- [ ] **Step 3: Stage the new external into `zz_stg` (needs user
      authorization)**

Ask the user to authorize, then per district, each in its own Bash call:

```bash
uv run dbt run-operation stage_external_sources --target staging --args "select: cambium.src_cambium__eoc" --vars '{cloud_storage_uri_base: gs://teamster-test/dagster/kippnewark, ext_full_refresh: true}' --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest/src/dbt/kippnewark
```

and the same with `kippcamden`. Serialize; never run them in parallel.

- [ ] **Step 4: Build the staging models into `zz_stg` (needs user
      authorization)**

Per district, own Bash call:

```bash
uv run dbt build --select stg_cambium__njsla stg_cambium__njgpa --target staging --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-cambium-eoc-ingest/src/dbt/kippnewark 2>&1 | tail -n 15
```

Expected: models build, every test passes (`unique` on `studenttestuuid`, scoped
`not_null` on `test_grade`, `accepted_values` on `subject` and `discipline`).

- [ ] **Step 5: Row checks via BigQuery MCP**

Run once with `kippnewark` and once with `kippcamden` in the dataset name:

```sql
select
    testcode in ('ALG01', 'ALG02', 'GEO01') as is_eoc,
    discipline,
    count(*) as n,
    countif(test_grade is not null) as test_grade_set,
    countif(assessmentgrade is not null) as assessmentgrade_set,
    countif(gradelevelwhenassessed is null) as grade_missing,
from `teamster-332318.zz_stg_kippnewark_cambium.stg_cambium__njsla`
group by is_eoc, discipline
```

and the same grouping against prod
`teamster-332318.kippnewark_cambium.stg_cambium__njsla` for the non-EOC
baseline.

Expected: Newark 382 EOC rows, Camden 122; all EOC rows `discipline = 'Math'`,
`test_grade_set = 0`, `assessmentgrade_set = 0`, `grade_missing = 0`. Non-EOC
row counts equal prod `kipp<region>_cambium.stg_cambium__njsla` counts.

- [ ] **Step 6: kipptaf CI**

The PR modifies kipptaf `int_pearson__all_assessments.sql`, so CI rebuilds it
from the `zz_stg` sources. Invoke `pr-ci-review` and watch the checks with
`gh pr checks <n> --json name,bucket,state`. Expected: green. If the union lacks
`gradelevelwhenassessed` for the cambium branches, Step 4 did not land the
rename in `zz_stg`.

- [ ] **Step 7: Process review**

Invoke `superpowers:receiving-code-review` for `claude-review` findings and post
a per-finding verdict comment.

---

### Task 5: Post-merge prod launch

- [ ] **Step 1: Launch the prod assets right after the deploy**

After the merge deploys, launch `kippnewark/cambium/eoc` and
`kippcamden/cambium/eoc`, partition `2026|Spring`, in prod with
`mcp__dagster-plus__launch_asset_run`, before the first automation tick requests
`stg_cambium__njsla`.

- [ ] **Step 2: Confirm prod**

Once `stg_cambium__njsla` rebuilds in both districts and kipptaf's union view
refreshes, run:

```sql
select
    _dbt_source_project,
    count(*) as n,
    countif(discipline = 'Math') as math,
    countif(test_grade is null) as grade_null,
from `teamster-332318.kipptaf_pearson.int_pearson__all_assessments`
where academic_year = 2025 and testcode in ('ALG01', 'ALG02', 'GEO01')
group by _dbt_source_project
```

Expected: `kippnewark` 382, `kippcamden` 122, every row Math and grade NULL.
Comment the counts on #5481.

- [ ] **Step 3: Open the follow-up issue**

Open an issue for the `rpt_tableau__academic_goals_rollup` Algebra filter
described in the spec's _Out of scope_ section, using
`.github/ISSUE_TEMPLATE/bug_report.md`, after asking the user.
