# PowerSchool `U_EXPECTATIONS` Extract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a recurring BigQuery extract of the `U_EXPECTATIONS`
PowerSchool extension table from Newark production via the existing Oracle ODBC
factory, plus a dbt staging model and district-level opt-outs for the three
districts that don't yet have the table.

**Architecture:** A single YAML entry in `assets-full.yaml` registers the asset
with the existing `build_powerschool_table_asset()` factory; the asset
auto-flows through the existing fiscal-year-partitioned PS sensor, GCS landing
path, and BigQuery loader. A dbt source entry in the shared `dbt/powerschool/`
package (with a sibling staging model) lets all consuming district projects
reference it; Camden/Miami/Paterson disable both source and model in their
`dbt_project.yml`.

**Tech Stack:** Dagster, Python 3.13, `oracledb`, `fastavro`, dbt-bigquery,
BigQuery external tables (Avro), pytest.

**Spec:**
[`docs/superpowers/specs/2026-05-08-powerschool-u-expectations-extract-design.md`](../specs/2026-05-08-powerschool-u-expectations-extract-design.md)

**Worktree root:**
`/workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-u-expectations`

All `git`, `uv run`, and tool invocations below assume that worktree as the
working directory. From other working directories use `git -C <worktree>` and
`--project-dir <worktree>/...` per CLAUDE.md.

---

## File Structure

| Path                                                                                                              | Action | Responsibility                                                                       |
| ----------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------ |
| `src/teamster/code_locations/kippnewark/powerschool/config/assets-full.yaml`                                      | modify | Register `u_expectations` as a fiscal-year-partitioned ODBC asset on `whenmodified`. |
| `tests/assets/test_assets_powerschool_sis.py`                                                                     | modify | Add `test_u_expectations_kippnewark` e2e test.                                       |
| `src/dbt/powerschool/models/sis/staging/odbc/sources-external.yml`                                                | modify | Declare `src_powerschool__u_expectations` as a BigQuery Avro external source.        |
| `src/dbt/powerschool/models/sis/staging/odbc/stg_powerschool__u_expectations.sql`                                 | create | Unwrap Avro NUMBER struct columns; pass through everything else.                     |
| `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__u_expectations.yml`                           | create | Contract column types + descriptions; uniqueness on `dcid`.                          |
| `src/dbt/kippcamden/dbt_project.yml`, `src/dbt/kippmiami/dbt_project.yml`, `src/dbt/kipppaterson/dbt_project.yml` | modify | Disable source + staging model (table not present in those instances).               |

---

## Task 1: Register the Dagster asset (TDD via e2e test)

**Files:**

- Test: `tests/assets/test_assets_powerschool_sis.py`
- Modify:
  `src/teamster/code_locations/kippnewark/powerschool/config/assets-full.yaml`

- [ ] **Step 1: Add the failing e2e test**

Edit `tests/assets/test_assets_powerschool_sis.py`. Insert this function
immediately before `def test_u_studentsuserfields_kippnewark():` (around line
85):

```python
def test_u_expectations_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_partitioned_asset(
        assets=assets,
        asset_name="u_expectations",
        code_location=CODE_LOCATION.upper(),
    )
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
uv run pytest tests/assets/test_assets_powerschool_sis.py::test_u_expectations_kippnewark -v
```

Expected: `IndexError: list index out of range` raised inside
`_test_partitioned_asset` at the line
`asset = [a for a in assets if a.key.path[-1] == asset_name][0]` — the asset
doesn't exist yet, so the list comprehension is empty.

If the test errors instead with `1Password` / env var / SSH-related messages
before reaching the IndexError, the local environment isn't authenticated. Set
`OP_SERVICE_ACCOUNT_TOKEN` (the user runs in a VS Code terminal, not via Claude)
and re-run.

- [ ] **Step 3: Add the asset YAML entry**

Edit
`src/teamster/code_locations/kippnewark/powerschool/config/assets-full.yaml`.
Append at the end of the file (after the existing `# whenmodified` group;
alphabetical order is not enforced — match existing trailing-entry style):

```yaml
- asset_name: u_expectations
  partition_column: whenmodified
```

Indent must be two spaces under `assets:` matching surrounding entries.

- [ ] **Step 4: Run the test against Newark Oracle and verify it passes**

```bash
uv run pytest tests/assets/test_assets_powerschool_sis.py::test_u_expectations_kippnewark -v
```

Expected: PASS. The test materializes a randomly chosen fiscal-year partition;
the assertion `result.success` plus a non-negative integer record count is
sufficient — zero rows is acceptable for older partitions because the plugin was
installed recently.

If the test fails with `ORA-00942: table or view does not exist`, the Oracle
table name needs investigation: connect via the SSH tunnel and run

```sql
select owner, table_name from all_tables where table_name = 'U_EXPECTATIONS';
```

If it's schema-qualified (e.g., owner is not `PS`), update the YAML `asset_name`
to `<owner_lower>.u_expectations`. SQLAlchemy uppercases unquoted identifiers,
so the lowercase YAML value resolves correctly.

If the test fails with the usual `whenmodified`-related partition mismatch
(table has the column but no rows in the chosen partition), re-run —
`_test_partitioned_asset` picks a random partition from the full fiscal-year
range starting 2016-07-01.

- [ ] **Step 5: Confirm Dagster definitions still load**

```bash
uv run dagster definitions validate -m teamster.code_locations.kippnewark.definitions
```

Expected: exit 0. Errors specific to env vars unavailable in this Codespace are
acceptable per `src/teamster/CLAUDE.md` ("`dagster definitions validate` may
mislead locally — env vars unavailable in codespace cause false errors"). What
you're confirming is that no asset-wiring error appears.

- [ ] **Step 6: Commit**

```bash
git add tests/assets/test_assets_powerschool_sis.py \
        src/teamster/code_locations/kippnewark/powerschool/config/assets-full.yaml
git commit -m "feat(powerschool): extract U_EXPECTATIONS from Newark Oracle (#3756)"
```

---

## Task 2: Add the dbt source entry and stage the BigQuery external table

**Files:**

- Modify: `src/dbt/powerschool/models/sis/staging/odbc/sources-external.yml`

- [ ] **Step 1: Add the source entry**

Open `src/dbt/powerschool/models/sis/staging/odbc/sources-external.yml`. Locate
the existing `src_powerschool__u_studentsuserfields` block (around line 891).
Insert the following block immediately after it, preserving two-space YAML
indentation under the parent `tables:` list:

```yaml
- name: src_powerschool__u_expectations
  config:
    meta:
      dagster:
        asset_key:
          - "{{ project_name }}"
          - powerschool
          - u_expectations
  external:
    location:
      "{{ var('powerschool_external_location_root',
      env_var('DBT_DEV_CLOUD_STORAGE_URI_BASE', '')) }}/u_expectations/*"
    options:
      connection_name: "{{ var('bigquery_external_connection_name') }}"
      metadata_cache_mode: MANUAL
      max_staleness: INTERVAL 7 DAY
      format: AVRO
      enable_logical_types: true
```

The block must mirror `src_powerschool__u_studentsuserfields` exactly except for
the table-name slug `u_expectations`.

- [ ] **Step 2: Verify dbt parses the new source**

```bash
uv run dbt parse --project-dir src/dbt/kippnewark --target prod --target-path target/prod
```

Expected: parse succeeds. If it fails with a YAML error, fix indentation. If it
fails with a Jinja error pointing at the new block, double-check the curly-brace
nesting against the precedent.

- [ ] **Step 3: Materialize the Dagster asset to land Avro in GCS**

The dbt external source points to
`gs://teamster-kippnewark/dagster/kippnewark/powerschool/u_expectations/*`.
Until the asset has materialized at least one partition,
`stage_external_sources` will create an empty BQ external table.

Trigger materialization through Dagster's UI (or re-run the e2e test from Task 1
— same effect, materializes one partition into the Hive-partitioned GCS path).

- [ ] **Step 4: Stage the external table to BigQuery**

```bash
uv run dbt run-operation stage_external_sources \
  --args 'select: powerschool_odbc.src_powerschool__u_expectations' \
  --project-dir src/dbt/kippnewark \
  --target staging
```

Expected: dbt prints `1 of 1 OK` and the table appears in BigQuery. Note from
`src/dbt/CLAUDE.md`: the source selector is `<source_name>.<table_name>`,
**not** project-qualified.

- [ ] **Step 5: Smoke-test the external table**

```bash
uv run dbt show \
  --inline "select count(*) as n from {{ source('powerschool_odbc', 'src_powerschool__u_expectations') }}" \
  --project-dir src/dbt/kippnewark \
  --target staging
```

Expected: returns a non-negative integer. Zero is acceptable if the plugin's
only populated partitions don't yet have ODBC-extracted Avro on disk; non-zero
confirms end-to-end raw-data pipe.

- [ ] **Step 6: Commit**

```bash
git add src/dbt/powerschool/models/sis/staging/odbc/sources-external.yml
git commit -m "feat(dbt-powerschool): add U_EXPECTATIONS external source (#3756)"
```

---

## Task 3: Add the dbt staging model

**Files:**

- Create:
  `src/dbt/powerschool/models/sis/staging/odbc/stg_powerschool__u_expectations.sql`
- Create:
  `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__u_expectations.yml`

- [ ] **Step 1: Profile the loaded raw table to confirm column shape**

```bash
uv run dbt show \
  --inline "select column_name, data_type from \`teamster-332318\`.kippnewark_powerschool.INFORMATION_SCHEMA.COLUMNS where table_name = 'src_powerschool__u_expectations' order by ordinal_position" \
  --project-dir src/dbt/kippnewark \
  --target staging
```

(Adjust dataset prefix to whatever `stage_external_sources` materialized to
under the staging target — likely `staging_kippnewark_powerschool` or similar;
check the result of Task 2 Step 4.)

Record which columns land as
`STRUCT<int_value INT64, decimal_value NUMERIC, ...>` (Avro NUMBER union → BQ
struct) versus plain types. Expected: `dcid`, `id`, `quarter`, `week_number`,
`cnt_w`, `cnt_h`, `cnt_f`, `cnt_s` arrive as structs; string/timestamp columns
are plain.

- [ ] **Step 2: Write the staging SQL**

Create
`src/dbt/powerschool/models/sis/staging/odbc/stg_powerschool__u_expectations.sql`:

```sql
with
    transformations as (
        select
            * except (dcid, id, quarter, week_number, cnt_w, cnt_h, cnt_f, cnt_s),

            /* column transformations */
            dcid.int_value as dcid,
            id.int_value as id,
            quarter.int_value as quarter,
            week_number.int_value as week_number,
            cnt_w.int_value as cnt_w,
            cnt_h.int_value as cnt_h,
            cnt_f.int_value as cnt_f,
            cnt_s.int_value as cnt_s,
        from {{ source("powerschool_odbc", "src_powerschool__u_expectations") }}
    )

select * from transformations
```

If Step 1 showed a column landing as plain `INT64` rather than a struct (e.g.,
the plugin wrote it as a Java int rather than an Oracle NUMBER), drop it from
the `* except (...)` list and the unwrap block. Likewise, if a count column
comes back as `NUMERIC` with non-zero scale, replace `.int_value` with
`safe_cast(... as int64)` for that column.

Note: no `dbt_utils.deduplicate` here — `dcid` is unique by construction (Oracle
auto-PK); the precedent in `stg_powerschool__u_clg_et_stu` deduplicates because
of `studentsdcid + exit_date` business-key collisions, which don't apply to a
raw-counts roll-up table.

- [ ] **Step 3: Write the properties YAML**

Create
`src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__u_expectations.yml`:

```yaml
models:
  - name: stg_powerschool__u_expectations
    description:
      Per-school-level / quarter / week roll-up of expectations counts (W/H/F/S)
      from the Newark Gradebook Audit plugin's U_EXPECTATIONS extension table.
      Always scoped to the current academic year — the source has no academic
      year column.
    columns:
      - name: dcid
        data_type: int64
        description:
          Auto-generated PowerSchool descendant ID. Primary key for this
          extension table.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
        constraints:
          - type: primary_key
      - name: id
        data_type: int64
        description: Plugin-assigned row identifier.
      - name: school_level
        data_type: string
        description:
          School-level grouping (e.g. ES / MS / HS) for the rollup row.
      - name: quarter
        data_type: int64
        description: Academic quarter (1-4) the rollup row covers.
      - name: week_number
        data_type: int64
        description: Week number within the quarter.
      - name: cnt_w
        data_type: int64
        description: Count of students in the W expectations bucket for the row.
      - name: cnt_h
        data_type: int64
        description: Count of students in the H expectations bucket for the row.
      - name: cnt_f
        data_type: int64
        description: Count of students in the F expectations bucket for the row.
      - name: cnt_s
        data_type: int64
        description: Count of students in the S expectations bucket for the row.
      - name: notes
        data_type: string
        description: Free-text notes captured by the plugin for the rollup row.
      - name: whocreated
        data_type: string
        description: User login that created the record.
      - name: whencreated
        data_type: timestamp
        description:
          Date and time the record was created. Defaults to system date.
      - name: whomodified
        data_type: string
        description: User login that last modified the record.
      - name: whenmodified
        data_type: timestamp
        description:
          Date and time the record was last modified. Defaults to system date.
```

If Step 1 showed any additional PS audit columns landing in the table that
aren't in this list (PS occasionally adds new ones), add them with `data_type`
matching the BQ column type — contract enforcement fails otherwise.

- [ ] **Step 4: Build the model and confirm it compiles + tests pass**

```bash
uv run dbt build \
  --select stg_powerschool__u_expectations \
  --project-dir src/dbt/kippnewark \
  --target staging
```

Expected: `1 of 1 OK created sql view model` + tests `dcid not_null` and
`dcid unique` both pass.

If contract enforcement fails (`Contract for model X has unmatched columns:`),
reconcile the YAML with the actual columns from Step 1.

- [ ] **Step 5: Lint check**

```bash
.trunk/tools/trunk check --force \
  src/dbt/powerschool/models/sis/staging/odbc/stg_powerschool__u_expectations.sql \
  src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__u_expectations.yml \
  src/dbt/powerschool/models/sis/staging/odbc/sources-external.yml
```

Expected: no issues. sqlfluff and yamllint enforce style; fix in place if
anything fires (don't add `# trunk-ignore` to bypass real issues).

- [ ] **Step 6: Commit**

```bash
git add src/dbt/powerschool/models/sis/staging/odbc/stg_powerschool__u_expectations.sql \
        src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__u_expectations.yml
git commit -m "feat(dbt-powerschool): add stg_powerschool__u_expectations (#3756)"
```

---

## Task 4: Disable in Camden / Miami / Paterson

**Files:**

- Modify: `src/dbt/kippcamden/dbt_project.yml`
- Modify: `src/dbt/kippmiami/dbt_project.yml`
- Modify: `src/dbt/kipppaterson/dbt_project.yml`

The Gradebook Audit plugin is only on Newark prod, so the asset/source/model
must be disabled in the other three districts to avoid `relation does not exist`
errors at parse and build time.

- [ ] **Step 1: Disable the model in each district**

In each of the three district `dbt_project.yml` files, find the existing
`models.powerschool.sis.staging.odbc.stg_powerschool__u_clg_et_stu_alt: { +enabled: false }`
block. Insert immediately after it (alphabetical order keeps the list
scannable):

```yaml
stg_powerschool__u_expectations:
  +enabled: false
```

Match the existing indentation exactly — three or four levels of two-space
nesting depending on the district file.

- [ ] **Step 2: Disable the source in each district**

In each of the three district `dbt_project.yml` files, find the existing
`sources.powerschool.staging.odbc.powerschool_odbc.src_powerschool__u_clg_et_stu_alt: { +enabled: false }`
block. Insert immediately after it:

```yaml
src_powerschool__u_expectations:
  +enabled: false
```

- [ ] **Step 3: Verify each district parses cleanly**

```bash
uv run dbt parse --project-dir src/dbt/kippcamden --target prod --target-path target/prod
uv run dbt parse --project-dir src/dbt/kippmiami --target prod --target-path target/prod
uv run dbt parse --project-dir src/dbt/kipppaterson --target prod --target-path target/prod
```

Expected: all three parse without error.

- [ ] **Step 4: Verify the model resolves as disabled (not built) in each
      non-Newark district**

```bash
uv run dbt list --select stg_powerschool__u_expectations --project-dir src/dbt/kippcamden --target prod
uv run dbt list --select stg_powerschool__u_expectations --project-dir src/dbt/kippmiami --target prod
uv run dbt list --select stg_powerschool__u_expectations --project-dir src/dbt/kipppaterson --target prod
```

Expected: each command prints "no nodes selected" or equivalent — i.e., the
model is correctly excluded from the graph.

- [ ] **Step 5: Verify Newark still includes the model**

```bash
uv run dbt list --select stg_powerschool__u_expectations --project-dir src/dbt/kippnewark --target prod
```

Expected: prints `powerschool.staging.stg_powerschool__u_expectations` (one
node).

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kippcamden/dbt_project.yml \
        src/dbt/kippmiami/dbt_project.yml \
        src/dbt/kipppaterson/dbt_project.yml
git commit -m "chore(dbt): disable u_expectations in non-Newark districts (#3756)"
```

---

## Task 5: Final verification and PR

- [ ] **Step 1: Re-run the e2e test to confirm nothing regressed**

```bash
uv run pytest tests/assets/test_assets_powerschool_sis.py::test_u_expectations_kippnewark -v
```

Expected: PASS.

- [ ] **Step 2: Re-run the full kippnewark dbt build for the staging model and
      any directly-touched dependents**

```bash
uv run dbt build --select +stg_powerschool__u_expectations --project-dir src/dbt/kippnewark --target staging
```

Expected: builds and tests pass. The `+` prefix selects upstream nodes; for a
staging model with only an external source as parent, this is just the model
itself plus its tests.

- [ ] **Step 3: Branch lint check**

```bash
.trunk/tools/trunk check --force \
  $(git diff --name-only origin/main...HEAD)
```

Expected: no issues. The `pre-push` hook runs the same check on push, so any
failure here would block the push anyway.

- [ ] **Step 4: Push the branch**

```bash
git push
```

If a push hook complains, address the root cause. Do not pass `--no-verify`.

- [ ] **Step 5: Open the PR**

Use `.github/pull_request_template.md` as the body. Title format:
`feat(powerschool): extract U_EXPECTATIONS from Newark Oracle (#3756)`.

```bash
gh pr create --title "feat(powerschool): extract U_EXPECTATIONS from Newark Oracle (#3756)" \
  --body "$(cat .github/pull_request_template.md)"
```

Update the populated PR body to reference issue #3756 in the description and
check off items in the template's checklist that apply.

- [ ] **Step 6: Verify branch deployment build**

After CI kicks off the dbt Cloud branch deployment, confirm:

1. `dbt build --select stg_powerschool__u_expectations` passes in the branch
   deployment's Newark project.
2. The Dagster branch deployment materializes the asset against Newark prod (one
   partition, latest fiscal year).

Both are run by the platform; you're checking the run status, not invoking them
manually.

---

## Notes for the Executing Agent

- This work is happening in a worktree at
  `/workspaces/teamster/.worktrees/cbini/feat/claude-powerschool-u-expectations`.
  **Always pass `--project-dir` / `git -C` explicitly when invoking from a
  different working directory.** Bare `git` from `/workspaces/teamster` commits
  to `main`.
- **Do not run** `trunk fmt` or `trunk check` proactively — the pre-commit hook
  formats; the pre-push hook checks. Use
  `.trunk/tools/trunk check --force <files>` only for the verification step in
  Task 3 Step 5 and Task 5 Step 3, where confirmation is required before
  claiming clean.
- **Do not** use `dbt_utils.deduplicate`, `select distinct`, or
  `qualify row_number() = 1` in the staging SQL. The model has a single primary
  key (`dcid`); deduplication is unnecessary and is explicitly an anti-pattern
  per `src/dbt/CLAUDE.md`.
- **Do not** add `+enabled: false` overrides to `kippnewark/dbt_project.yml` —
  Newark is the only district where this asset is enabled by default.
- **Do not** add a per-model `contract: { enforced: true }` block in the
  properties YAML — contract enforcement is set at the directory level in
  `src/dbt/powerschool/dbt_project.yml`.
- **Do not** introduce a new schedule, sensor, job, intermediate, or mart model.
  Spec section 6 explicitly defers all downstream modeling to a separate plan.
- If any Oracle / SSH / 1Password env-var-related test failure surfaces, surface
  it to the user — Claude sessions cannot access secrets. Re-running in a VS
  Code terminal where `OP_SERVICE_ACCOUNT_TOKEN` is set is the correct fix.
