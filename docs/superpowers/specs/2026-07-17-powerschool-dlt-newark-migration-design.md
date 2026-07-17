# PowerSchool dlt migration: kippnewark — design

Issue: [#4427](https://github.com/TEAMSchools/teamster/issues/4427) (Newark
slice only). Builds on the Paterson pilot
([#4415](https://github.com/TEAMSchools/teamster/pull/4415), spec
`2026-07-16-powerschool-dlt-probe-gated-sync-design.md`).

## Scope

Migrate kippnewark's PowerSchool SIS ingestion from the ODBC/Avro/GCS path to
the shared dlt factory (`libraries/dlt/powerschool/`), retire Newark's ODBC path
in the same PR, and fold in two migration-timed refactors: #4423 (inject Oracle
credentials as a resource) and #4424 part 1 (centralize the paramiko SSH
resource construction). Camden, the kippmiami cleanup, and the final ODBC
teardown are separate follow-up PRs.

## Spike results (PR #4429, branch deployment, 2026-07-17)

Measured against Newark's production Oracle over the SSH tunnel:

| Measurement                                       | Result                                                               |
| ------------------------------------------------- | -------------------------------------------------------------------- |
| `attendance` full extract, driver `arraysize=100` | ~2.4-2.6k rows/s — latency-bound at ~40ms RTT (~40 min for 5.8M)     |
| `attendance` full extract, `arraysize=10_000`     | **49.6k rows/s** — 5,825,606 rows in 117s extract + 34s BQ load      |
| SSH                                               | `enable_legacy_rsa=True` paramiko tunnel works against Newark's host |
| Probe gate                                        | works (`1/1 changed` on first run)                                   |
| Untrimmed `cc` / `log` / `u_studentsuserfields`   | all load cleanly — 42 / 52 / 349 columns, 3 tables in one 56s step   |

Conclusions:

- The bottleneck was the driver's 100-row fetch batches over the WAN, not the
  tunnel, Oracle, or dlt. `create_engine(..., arraysize=10_000)` is a ~20x fix.
- At ~50k rows/s, **naive probe-gated full replace serves every Newark table**:
  `assignmentscore` (19.2M rows) ≈ 7-9 min nightly, `attendance` (5.8M) ≈ 3 min
  intraday, one-time initial load (~36.4M rows across ~57 tables) ≈ 15 min. The
  windowed/partitioned replace strategy contemplated in #4427 and #3807 is **not
  needed**.
- Newark's code-server container needs `PS_SSH_PASSWORD` (execution-plan
  resource resolution happens there, not only in run pods) — fixed in
  `dagster-cloud.yaml`.
- **No column selection needed.** The ODBC `select_columns` trims existed to
  contain the hand-maintained Avro schema surface, which dlt (inferred schema)
  doesn't have. Untrimmed extracts of all three trimmed tables — including
  `u_studentsuserfields` with 349 Newark custom columns — reflect and load with
  no type failures. The raw dataset holds the full width; the dbt staging models
  still select the narrow column set, governing downstream exposure.

## Design

### 1. Library: `libraries/dlt/powerschool/assets.py`

- Keep `arraysize=10_000` on the extract engine (already committed; Paterson
  inherits the speedup through the shared factory).
- **No `included_columns` axis** — spike-disproven (see above). If a future
  table surfaces an unloadable column type, `table_rows` already accepts
  `included_columns`/`excluded_columns`, so the knob is a small additive change
  kept in the back pocket, not built speculatively.
- **#4423**: replace the `os.getenv`-based `_oracle_connection_url()` with an
  injected `ConfigurableResource` (`OracleResource` or similarly named: `user`,
  `password`, `host`, `port`, `service_name`, all `EnvVar`-backed; exposes
  `connection_url()`). The `@dlt_assets` op takes it as a resource argument
  bound to the `db_powerschool` key — free in the same PR because ODBC
  retirement removes the old `PowerSchoolODBCResource` binding — and the factory
  no longer reads process environment directly.

### 2. Core: `get_powerschool_ssh_resource()` (#4424 part 1)

Extend the shared factory in `core/resources.py` with
`password=EnvVar("PS_SSH_PASSWORD")` and `enable_legacy_rsa=True` (both
spike-proven for Newark; Paterson already runs this shape). Delete Paterson's
local `SSH_POWERSCHOOL` from `code_locations/kipppaterson/resources.py` and wire
both districts through the shared function. The extra fields are inert for the
remaining ODBC districts (sshpass reads the mounted password file, not the
resource field), so Camden/Miami are unaffected until their own migrations.

### 3. Code location: `code_locations/kippnewark/powerschool/sis/dlt/`

Mirror Paterson's layout (`assets.py`, `config/assets.yaml`, `schedules.py`):

- **Table scope**: the union of Newark's five ODBC config files (~57 active
  tables; commented-out tables stay out). Per-table `cursor_column` from the
  incumbent `partition_column` (`transaction_date` / `whenmodified`);
  no-partition tables get `cursor_column: null`.
- **Tiers**: `intraday` (15-min schedule) for the cursor-bearing tables the ODBC
  sensor refreshes today — including `attendance`, `storedgrades`,
  `pgfinalgrades`; `nightly` for gradebook tables (`assignmentscore`,
  `assignmentsection`, `assignmentcategoryassoc`, gradebook config tables) and
  all no-cursor tables. Schedule builder validates that intraday tables have
  cursors (as in Paterson's `schedules.py`).
- **`dagster-cloud.yaml`**: `PS_SSH_PASSWORD` added to the code-server container
  (already committed); run-pod config already complete.
- **`definitions.py`**: `dlt: DagsterDltResource()`, shared `ssh_powerschool`,
  new Oracle resource; ODBC wiring removed (below).

### 4. dbt: `src/dbt/kippnewark/dbt_project.yml`

Flip the shared `powerschool` package variants for kippnewark:
`staging/dlt +enabled: true`, `staging/odbc +enabled: false`. Carry the
per-model disables from the odbc block into the dlt block
(`stg_powerschool__gpprogresssubjectrequested`,
`stg_powerschool__gpprogresssubjectwaived` — tables not extracted). No source
edits: the `powerschool_dlt` source schema templates by `project_name`, and its
asset-key meta already carries the `sis` segment.

### 5. ODBC retirement (Newark only)

Delete `code_locations/kippnewark/powerschool/{assets,schedules,sensors}.py` and
`config/*.yaml` (ODBC), removing the sensor, both schedules, and the
`db_powerschool` (`PowerSchoolODBCResource`) wiring from `definitions.py`. The
library `libraries/powerschool/sis/odbc/` stays until Camden and Miami are off
it (final-teardown phase of #4427).

### 6. Go-live sequence

1. Merge; wait for the kippnewark location deploy.
1. `DROP SCHEMA dagster_kippnewark_dlt_powerschool CASCADE` (mandatory: spike
   runs already wrote migration-era tables to this dataset).
1. Set the `dlt_powerschool_kippnewark` concurrency pool to limit 1.
1. Launch the initial full load (all tables); verify per-table `row_count`
   against ODBC-era staging counts.
1. Regenerate `docs/automations.md` (`uv run scripts/gen-automations-doc.py`).

## Validation

- Branch deployment: launch a multi-table subset (small + trimmed + large) and
  verify row counts, trimmed column lists, and probe idle-tick behavior on a
  second run.
- dbt: `uv run dbt build --select staging.dlt --target staging` equivalents per
  repo conventions; dbt Cloud CI on the PR builds `state:modified+`.
- Compare `stg_powerschool__*` dlt-variant row counts to prod ODBC-variant
  counts for the same tables before flipping downstream marts.

## Out of scope

- kippcamden migration (next PR; near-mechanical once this lands).
- kippmiami PowerSchool ODBC deletion.
- Final ODBC library teardown, sshpass/Dockerfile cleanup (#4427 checklist),
  PowerSchool enrollment retirement (#4428).
- #4425 (shared `DagsterDltTranslator` base) — optional, not taken here.
