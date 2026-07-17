# Design: PowerSchool via dlt — kipppaterson pilot

Tracked in [#3807](https://github.com/TEAMSchools/teamster/issues/3807). Spike:
[#4398](https://github.com/TEAMSchools/teamster/issues/4398) /
[2026-07-14-powerschool-odbc-elt-spike-results.md](2026-07-14-powerschool-odbc-elt-spike-results.md).

## Goal

Replace the homegrown PowerSchool ODBC sync with dlt, piloted at `kipppaterson`.
Paterson is the one district without live ODBC today — its PowerSchool data
arrives as CSV drops over Couchdrop SFTP (26 tables). The pilot gives Paterson a
live Oracle connection via dlt at **full ODBC parity** (~57 tables, matching
`kippnewark`'s table set), retires the Couchdrop path, and establishes the
template the ODBC districts (`kippnewark`, `kippcamden`, `kippmiami`) migrate
onto afterward.

## Decisions (from brainstorming)

1. One design covering both the Dagster/dlt ingestion layer and the dbt staging
   rework — for Paterson the staging swap is the acceptance test.
1. Full ODBC parity table set (~57 tables), not just Paterson's current 26.
1. Cutover validated pre-merge on the PR's branch deployment; **single PR**.
1. Tiered cron schedules matching `kippnewark`'s cadence; no sensors, no Oracle
   staleness probes.
1. **Full refresh everything at Paterson.** Every table uses dlt
   `write_disposition="replace"` (free `LOAD` jobs, no cursor state, no boundary
   edge cases). Partitioned windowed replace — needed only at Newark-scale
   (31.5M-row `assignmentscore` vs Paterson's 270k) — is designed in the Newark
   migration, against real volumes. The per-table `load_strategy` config knob
   ships now so it slots in without reshaping.
1. The paramiko in-process SSH forward is **in scope** (replaces the `sshpass`
   subprocess for the dlt path only).
1. Asset keys drop the `dlt` layer: `[code_location, "powerschool", <table>]` —
   matching the incumbent ODBC districts' convention so later migrations are
   key-preserving swaps.

## Architecture

### Library: `src/teamster/libraries/dlt/powerschool/`

New dlt sub-library following illuminate/focus/zendesk:

- `assets.py` — `build_powerschool_dlt_assets(...)` factory modeled on
  `libraries/dlt/focus/assets.py`: one `@dlt_assets` per table.
  - `sql_database` source: `schema="ps"`, `backend="pyarrow"`,
    `defer_table_reflect=True`, `reflection_level="full_with_precision"`,
    `table_adapter_callback=remove_nullability_adapter`.
  - Oracle type adapter (`type_adapter_callback`) so decimals land as `NUMERIC`,
    not `FLOAT64`/`BIGNUMERIC` (spike caveat).
  - `PowerSchoolDagsterDltTranslator`: asset keys
    `[code_location, "powerschool", <table>]`, kind `oracle`.
  - The asset body opens the SSH tunnel before `dlt.run()` and points the
    connection string at the local forward port.
  - Dagster pool `dlt_powerschool_<code_location>` caps concurrent Oracle
    connections (focus/illuminate pattern).
- No collision with Paterson's SFTP assets during development — those key as
  `kipppaterson/powerschool/sis/sftp/<table>`.

### SSH tunnel: paramiko in-process forward

`SSHResource` already runs paramiko (with legacy `ssh-rsa` re-enabled) for SFTP.
Add a paramiko-based port-forward method:

- Password from an env-var-backed resource field — no `sshpass` subprocess, no
  mounted password file, no readiness race.
- Host-key verification kept (unlike Sling's `InsecureIgnoreHostKey`).
- Connect wrapped with tenacity per the repo retry pattern (transient subclasses
  only), on the connect path.
- The incumbent `sshpass` path stays untouched; ODBC districts are unaffected.
  Full retirement happens when the last ODBC district migrates.

### Code location: `code_locations/kipppaterson/powerschool/sis/dlt/`

Replaces `powerschool/sis/sftp/` (removed in the same PR):

- `config/assets.yaml` — ~57 entries: `table_name`, `load_strategy` (only
  `full_refresh` valid in the pilot) and `schedule_tier` (`intraday` |
  `nightly`).
- `assets.py` — builds per-table assets from YAML via the library factory.
- `schedules.py` — two `ScheduleDefinition`s:
  - intraday (`*/15 * * * *` ET): tables in `kippnewark`'s sensor-driven sets
    (full / no-partition / transaction-date). Blind 15-minute full refreshes are
    safe — `LOAD` jobs are free and Oracle reads are free; the pool bounds
    concurrency.
  - nightly (2am ET): gradebook-class tables (Newark's `assets-gradebook-*`
    sets).
- Resources: `ssh_powerschool` + Oracle `ConnectionStringCredentials` from the
  `op-ps-db-kipppaterson` / `op-ps-ssh-kipppaterson` secrets (provisioned for
  the spike, `dagster-cloud` namespace).

### BigQuery landing

Dataset `dagster_kipppaterson_dlt_powerschool` (focus/illuminate naming). Native
BQ tables, keyless ADC load jobs, no GCS staging.

## dbt staging layer

Third staging variant in the shared `powerschool` package:
`src/dbt/powerschool/models/sis/staging/dlt/` (~57 models), alongside `odbc/`
(82) and `sftp/` (65). Each model:

- Reads a `powerschool_dlt` source resolving to
  `dagster_<code_location>_dlt_powerschool` per district project — the models
  are template-reusable as-is by later migrations.
- Reads scalar numerics directly — no `STRUCT`-union unpacking (the incumbent
  odbc pattern dies here).
- Casts dlt's `TIMESTAMP` to `DATE` where the incumbent staging exposes `DATE`;
  `cast(... as numeric)` where reflection lands `BIGNUMERIC` (spike caveats).
- Keeps the same output contract (column names/types) as the corresponding
  `sftp`/`odbc` variant, so everything downstream of `stg_powerschool__*` is
  untouched. Contracts are enforced (`+contract` is on in the shared package),
  making shape-parity machine-checked.

The Paterson project swap is dbt config only: disable the `sftp` variants,
enable the `dlt` variants. Both variants materialize under the same
`stg_powerschool__*` names, so they cannot be enabled simultaneously in one
project — parity validation compares raw dlt tables against the live SFTP-fed
staging tables instead (below).

## Cutover (single PR)

1. The PR contains everything: dlt library, Paterson assets/schedules, the
   `staging/dlt` dbt variants, the Paterson sftp→dlt swap, removal of the SFTP
   powerschool assets/config, and doc updates (`kipppaterson/CLAUDE.md`,
   regenerated `reference/automations.md`).
1. On the PR's branch deployment (the spike's workflow), materialize the dlt
   assets against Paterson Oracle. dlt writes to BigQuery regardless of
   deployment, and `dagster_kipppaterson_dlt_powerschool` is a new dataset with
   no consumers — populating it from the branch is safe and pre-seeds prod.
1. Parity validation pre-merge (aggregates only in any external write — no PII):
   - 26 overlapping tables: row counts, key-set equality (e.g. `dcid`), spot
     value checks on the divergence-prone classes (dates, numerics, free text
     with embedded newlines).
   - ~31 net-new tables: no incumbent to compare; dbt contract enforcement +
     non-empty checks.
1. dbt Cloud CI builds the new staging variants + downstream off the populated
   dataset. CI may fire on push before branch-deployment materializations finish
   — expect one re-trigger once tables exist.
1. Merge. Prod schedules take over the same dataset (first prod run is just
   another full refresh). Rollback = revert the PR — the Couchdrop feed keeps
   flowing until Ops is explicitly told to stop it, so the SFTP path resumes on
   revert.

Trade-off accepted: a large PR and no prod soak period running both paths; the
safety net is branch-deployment validation plus single-PR revert. The spike
already de-risked the mechanism.

## Error handling

- Transient Oracle/tunnel failures: no bespoke retry loop — the next 15-minute
  tick is the retry (a full refresh is cheap; the incumbent's retry machinery
  existed because probes + partitions made runs expensive). Tunnel connect gets
  the standard tenacity wrap.
- `full_with_precision` reflection + `remove_nullability_adapter` prevents
  upstream `NOT NULL`/type drift from breaking `replace` loads (focus learning).
- dbt contracts are the schema-drift alarm: new/retyped PowerSchool columns land
  in the raw table, and the contract-enforced staging model fails loudly rather
  than silently shifting types downstream.

## Testing

- `uv run dagster definitions validate` / module import for `kipppaterson`.
- pytest for the factory: asset key shape, YAML parsing, tier→schedule
  assignment.
- Branch-deployment smoke run against Paterson Oracle covering at least one
  table from each schedule tier, plus the full parity validation above.
- dbt Cloud CI (`state:modified+`) proves staging + downstream on the PR schema.

## Out of scope

- Windowed partitioned replace (Newark migration design work).
- `enrollment/` REST API and Postgres dlt syncs.
- Retiring the `sshpass` path for the incumbent ODBC districts.
- Other districts' migrations (near-mechanical after this pattern proves).
