# PowerSchool ODBC SIS teardown — design

Combines issues [#4441](https://github.com/TEAMSchools/teamster/issues/4441)
(remove kippmiami's legacy PowerSchool ODBC stack) and
[#4442](https://github.com/TEAMSchools/teamster/issues/4442) (tear down the
shared legacy ODBC SIS library) into one PR. Parent: #4427.

## Context (verified 2026-07-17)

- Paterson (#4415), Newark (#4429), and Camden (#4440) migrated PowerSchool SIS
  ingestion from ODBC to dlt and are merged. All three have dbt
  `odbc.+enabled: false`.
- Miami's SIS moved to Focus (`code_locations/kippmiami/dlt/focus/`). Miami is
  the **sole** remaining importer of
  `src/teamster/libraries/powerschool/sis/odbc/` and the only district with the
  dbt `odbc` variant enabled.
- Miami's PowerSchool pipeline is already dormant in prod: the
  `kippmiami__powerschool__sis__*` schedules and asset sensor are STOPPED; last
  materialization of `kippmiami/powerschool/students` was ~2026-07-01 (3,946
  records). The `kippmiami_powerschool` BigQuery dataset is a frozen end-of-FY26
  snapshot.
- The autocomm push-back schedule
  (`kippmiami__extracts__powerschool__asset_job_schedule`) is also STOPPED.
- kipptaf dependence is wide: ~50 kipptaf models union
  `source("kippmiami_powerschool", ...)` (the whole cross-district powerschool
  staging/intermediate layer plus `int_students__contacts`); the source file
  declares ~95 tables with the target-conditional schema pattern and
  `meta.dagster.asset_key` pointers at Miami assets.
- Miami's live `int_fldoe__all_assessments` refs `stg_powerschool__students` and
  `stg_powerschool__u_studentsuserfields` solely to build a `student_number` ↔
  `fleid` lookup for joining FLDOE assessment files. kipptaf consumes Miami
  fldoe models, so Miami's dbt project must keep parsing.
- The "ODBC" stack never used pyodbc — it reads Oracle via `oracledb` through an
  sshpass SSH tunnel. The surviving dlt path shares its entire Python dependency
  footprint (`oracledb` via the `oracle+oracledb://` SQLAlchemy dialect,
  `sqlalchemy`, `dagster-ssh`, `fastavro`, `tenacity`).

## Decisions

1. **Keep Miami's pre-Focus PowerSchool history in network marts**, served from
   the frozen `kippmiami_powerschool` BigQuery tables (which must never be
   dropped).
2. **Delete the autocomm push-back entirely** (extract config, job/schedule
   wiring, Miami's two thin wrapper models). The kipptaf-level
   `rpt_powerschool__autocomm_*` models stay for the NJ districts; frozen Miami
   rows in them are unused and harmless.
3. **Archive the shared libraries in place — do not delete or comment out.** The
   Python ODBC library and the dbt `staging/odbc` models stay byte-for-byte
   intact; only their references are removed. Unreferenced Python modules are
   never imported and disabled dbt models never build, so no import or parse
   errors result.
4. **Fold in the SSH method rename**: remove the sshpass `open_ssh_tunnel()`
   from `SSHResource` and rename `open_ssh_tunnel_paramiko` → `open_ssh_tunnel`.

## Scope

### 1. Downstream repoints (same PR, non-mechanical)

- **kipptaf**: convert
  `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml` to a BQ-native
  frozen source — hardcoded `kippmiami_powerschool` schema (no
  target-conditional prefix), drop every `meta.dagster.asset_key` block (the
  Miami assets are being deleted; leaving them would dangle in kipptaf's asset
  graph). Add a source `description` stating this is a frozen pre-Focus archive
  that must not be dropped. All ~50 kipptaf union models compile unchanged.
- **kipptaf fldoe** (`src/dbt/kipptaf/models/fldoe/sources-kippmiami.yml`) stays
  as-is — Miami fldoe keeps building live.
- **kippmiami fldoe**: add a BQ-native source (`sources-bigquery.yml`, schema
  `kippmiami_powerschool`) declaring `stg_powerschool__students` and
  `stg_powerschool__u_studentsuserfields`; switch the two `ref()`s in
  `int_fldoe__all_assessments` to `source()`.

### 2. kippmiami teardown (delete — Miami-specific dead code only)

- `code_locations/kippmiami/powerschool/` (assets, schedules, sensors, config)
  and its wiring in `definitions.py` (module import, schedules, sensors,
  `db_powerschool`, `ssh_powerschool` resources).
- `code_locations/kippmiami/extracts/config/powerschool.yaml` plus its
  job/schedule entry (the focus extract stays).
- Miami dbt: `models/extracts/powerschool/` (both `rpt_powerschool__autocomm_*`
  wrappers + properties), `models/powerschool/` (the
  `stg_powerschool__u_studentsuserfields` override), the `powerschool` entry in
  `packages.yml`, and both `odbc` enable-blocks in `dbt_project.yml`.
- `dagster-cloud.yaml`: all `PS_DB_*` / `PS_SSH_*` entries and the mounted
  SSH-password-file volume, in BOTH the `container_context` and `run_k8s_config`
  blocks.
- `.k8s/1password/items.yaml`: remove the `op-ps-db-kippmiami` and
  `op-ps-ssh-kippmiami` items. Cluster-side apply/delete is handed to the user
  per `.k8s/` conventions.
- `.github/workflows/deploy-prod-kippmiami.yaml`: drop `src/dbt/powerschool/**`
  (Miami no longer imports the package) and
  `src/teamster/libraries/powerschool/sis/odbc/**` from its paths.

### 3. Shared library archival + live-code cleanup

- `src/teamster/libraries/powerschool/sis/odbc/` — **unchanged** (archive). Its
  tests under `tests/libraries/powerschool/sis/odbc/` stay and must keep
  passing.
- `src/teamster/core/resources.py`: remove the `PowerSchoolODBCResource` import
  and `DB_POWERSCHOOL`. Keep `get_powerschool_ssh_resource()` and
  `get_powerschool_oracle_resource()` (dlt path; Newark/Camden/Paterson).
- `src/teamster/libraries/ssh/resources.py`: remove the sshpass
  `open_ssh_tunnel()` method (and its subprocess-stdout exception if nothing
  else uses it); rename `open_ssh_tunnel_paramiko` → `open_ssh_tunnel`. Update
  the one live caller (`libraries/dlt/powerschool/assets.py`) and
  `tests/libraries/test_ssh_paramiko_tunnel.py`. The archived odbc lib's
  `open_ssh_tunnel()` calls would now bind to the paramiko method if ever
  revived — dead code; noted in the PR body. If the archived odbc test suite
  mocks the removed sshpass method, adjust minimally (or exclude) so the suite
  stays green.
- Dockerfile: remove `sshpass` AND `openssh-client` from the apt install
  (verified: the only `ssh`-binary consumer was the sshpass subprocess; the
  paramiko tunnel is pure Python; git/dbt fetches are https). Keep `oracledb`
  and `dagster-ssh` Python deps — no `pyproject.toml` changes.
- Newark + Camden `dagster-cloud.yaml`: remove the leftover SSH-password-file
  volume mounts (dead since their dlt migrations; Paterson has none). Their
  `PS_DB_*` / `PS_SSH_*` entries stay — the dlt tunnel uses them.

### 4. dbt powerschool package (archive + default off)

- `models/sis/staging/odbc/` and the odbc sources file — **unchanged**
  (archive).
- Package `dbt_project.yml`: default the odbc variant to `+enabled: false` for
  both models and sources.
- Remove the now-redundant `odbc: +enabled: false` override blocks from
  Newark/Camden/Paterson `dbt_project.yml` (models + sources).

## Out of scope

- #4424 part 2 (sshtunnel.SSHTunnelForwarder evaluation) — the paramiko
  implementation is renamed, not re-evaluated.
- #4425 (shared DagsterDltTranslator base).
- #4428 (PowerSchool enrollment retirement) — separate product line.
- Focus → network-marts integration for Miami current-year data (including the
  Focus-based FLEID lookup — see Follow-ups).

## Verification

1. `uv run python -c "import teamster.code_locations.<loc>.definitions"` for
   kippmiami, kippnewark, kippcamden, kipppaterson (after
   `dagster-dbt project prepare-and-package`).
2. `uv run dbt parse` for kippmiami, kipptaf, and the three NJ district
   projects.
3. `dbt compile` spot-checks: `int_fldoe__all_assessments` (kippmiami) and one
   kipptaf union model, confirming the frozen sources resolve to
   `kippmiami_powerschool` in every target.
4. `uv run pytest tests/libraries/test_ssh_paramiko_tunnel.py tests/libraries/powerschool/`
   — rename callers updated, archive suite green.
5. Grep sweeps (`--include='*.{sql,yml,md,py}'`) for `DB_POWERSCHOOL`,
   `sshpass`, `open_ssh_tunnel_paramiko`, `powerschool_odbc`, and `sis.odbc` /
   `sis/odbc` imports — no survivors outside the archived directories and this
   spec.

## Risks / notes

- Editing `sources-kippmiami.yml` marks the whole source modified → dbt Cloud CI
  `state:modified+` rebuilds every kipptaf model reading it (~50+). Expected;
  the BQ-native conversion is what prevents `Table not found` on clone-skipped
  staging copies.
- The frozen `kippmiami_powerschool` dataset must never be dropped; the source
  description says so.
- The archived odbc library becomes non-runnable in the image (tunnel binaries
  removed) while staying importable and test-covered — archive, not zombie.
- Miami students enrolling after July 2026 have no FLEID mapping, so their
  future FAST/EOC rows drop out of `int_fldoe__all_assessments` until the
  follow-up lands.

## Follow-ups (separate issues)

1. Focus-based FLEID lookup to replace the frozen
   `stg_powerschool__u_studentsuserfields` join in `int_fldoe__all_assessments`
   (Focus carries FLEID).
