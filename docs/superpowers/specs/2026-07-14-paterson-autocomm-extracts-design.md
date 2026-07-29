# Paterson PowerSchool autocomm extracts + Couchdrop path redirect

- **Issue**: [#4399](https://github.com/TEAMSchools/teamster/issues/4399)
- **Date**: 2026-07-14
- **Status**: Approved design

## Goal

Extend the PowerSchool autocomm extracts (students and teachers; no IEP for now)
to `kipppaterson`, and redirect the autocomm Couchdrop destination folder for
all four districts to a new `data-team/` root.

## Background

Newark, Camden, and Miami already run autocomm extracts on this pattern:

1. Network-level kipptaf models (`rpt_powerschool__autocomm_students`,
   `rpt_powerschool__autocomm_teachers`,
   `rpt_powerschool__autocomm_students_iep`) compute the extract for all
   districts, tagged with a `code_location` column.
2. Each district dbt project has thin `rpt_powerschool__autocomm_*` models
   filtering `where code_location = '{{ project_name }}'` against the
   `kipptaf_extracts` source.
3. Each district code location has an `extracts/` Dagster module:
   `build_bigquery_query_sftp_asset` queries the district table and uploads a
   tab-delimited headerless `.txt` to Couchdrop on a 3am daily schedule.

The kipptaf models already carry Paterson rows (553 students, 91 teachers as of
2026-07-14), so this change is plumbing only. Paterson's PowerSchool _ingestion_
is SFTP-based (no ODBC), but that does not affect the extract side, which reads
from BigQuery.

## Design

### 1. dbt — `src/dbt/kipppaterson`

- New `models/extracts/sources.yml` declaring the `kipptaf_extracts` source with
  `rpt_powerschool__autocomm_students` and `rpt_powerschool__autocomm_teachers`
  tables (no IEP entry), each carrying the Dagster `asset_key` meta
  (`kipptaf/extracts/<table>`) so cross-location lineage resolves — copy
  Newark's file minus the IEP table.
- New `models/extracts/powerschool/rpt_powerschool__autocomm_students.sql` and
  `rpt_powerschool__autocomm_teachers.sql`, copied from **Newark** (Paterson is
  an NJ district, so it keeps the NJ-specific columns:
  `s_nj_stu_x__graduation_pathway_math`/`_ela`,
  `u_studentsuserfields__studentemail`, `s_stu_x__fafsa`). The
  `where code_location = '{{ project_name }}'` filter resolves to `kipppaterson`
  automatically.
- Matching `properties/` YAMLs copied from Newark (contracts + descriptions).
- New `models/exposures/powerschool.yml` exposure depending on the two models
  (students + teachers only).
- `dbt_project.yml`: add `extracts: +schema: extracts` under `models:` so the
  models land in `kipppaterson_extracts`.

### 2. Dagster — `src/teamster/code_locations/kipppaterson`

- New `extracts/` module mirroring Newark:
  - `config/powerschool.yaml` — two assets (students, teachers) with
    `query_config` schema `kipppaterson_extracts`, file stems
    `powerschool_autocomm_students` / `powerschool_autocomm_teachers_accounts`,
    suffix `txt`, tab delimiter, no header, and the new Couchdrop destination
    path (below).
  - `assets.py` — builds assets from the YAML via
    `build_bigquery_query_sftp_asset(code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a)`.
  - `jobs.py` — `kipppaterson__extracts__powerschool__asset_job`.
  - `schedules.py` — `ScheduleDefinition`, cron `0 3 * * *`, America/New_York.
  - `__init__.py` — exports `assets`, `schedules`.
- `definitions.py`: register the extracts assets and schedule; add
  `"db_bigquery": BIGQUERY_RESOURCE` to resources (`gcs` and `ssh_couchdrop` are
  already present).
- Update `kipppaterson/CLAUDE.md`: remove the "no `db_bigquery` resource" and
  "no extracts module" claims; add `extracts` to the Active Integrations table.

### 3. Couchdrop path redirect — all four districts

In each district's `extracts/config/powerschool.yaml` (`kippnewark`,
`kippcamden`, `kippmiami`, and the new `kipppaterson`), set every autocomm
`destination_config.path` to:

```text
data-team/<code_location>/powerschool/autocomm
```

e.g. `data-team/kipppaterson/powerschool/autocomm` (replacing
`teamster-<code_location>/couchdrop/powerschool`). Newark's IEP extract moves
with the other two. The SFTP uploader auto-creates missing directories, so no
folder pre-provisioning is needed.

Only the autocomm PowerSchool extract configs move; other Couchdrop destinations
are out of scope.

### Out of scope

- Paterson `rpt_powerschool__autocomm_students_iep` (may follow later).
- Any change to the kipptaf network models (Paterson rows already present).
- PowerSchool AutoComm / Couchdrop configuration outside this repo.

## Coordination risk

PowerSchool's AutoComm import jobs (and any Couchdrop routing rules) currently
read from the old folders. They must be repointed when this merges, or imports
go stale silently. Sequence the merge with the owner of the PowerSchool AutoComm
configuration.

## Validation

1. `uv run dbt parse` for `kipppaterson`; build the two new models with
   `--target dev --defer --state <abs prod manifest>` and spot-check row counts
   against the kipptaf table (553 students / 91 teachers at design time).
2. `uv run python -c "import teamster.code_locations.kipppaterson.extracts"`
   from the worktree (full `definitions` import fails in Codespace on unset
   PowerSchool variables by design; Paterson has no PowerSchool ODBC resource,
   but the submodule import check is the repo-standard validation anyway).
3. dbt Cloud CI on the PR (new models are `state:modified+`).
4. Post-merge: confirm the 3am schedule run uploads both files to the new
   Couchdrop folder, and existing districts' extracts land under `data-team/`.
