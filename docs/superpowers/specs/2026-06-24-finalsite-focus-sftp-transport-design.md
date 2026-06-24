# Finalsite → Focus SFTP transport (Component 5)

- **Issue:** [#4207](https://github.com/TEAMSchools/teamster/issues/4207)
- **Parent:** [#4073](https://github.com/TEAMSchools/teamster/issues/4073) —
  Finalsite → Focus enrollment integration (KIPP Miami)
- **Status:** Design approved; ready for implementation plan

## Summary

Build the transport seam that renders the five Focus-shaped output models to
coordinated CSVs and delivers them to Focus over SFTP. Component 4
([#4201](https://github.com/TEAMSchools/teamster/issues/4201)) built the
`rpt_focus__*` output models; nothing yet pushes them to Focus. This component
adds that push using the existing `build_bigquery_query_sftp_asset` factory — no
library changes, mostly YAML config plus one new SSH resource.

## Context

The five Focus SFTP template layouts are produced by `rpt_focus__*` models:

- `rpt_focus__demographics`
- `rpt_focus__student_enrollment`
- `rpt_focus__addresses`
- `rpt_focus__contacts`
- `rpt_focus__linked_students`

The authoritative models live in the **kipptaf** dbt project
(`src/dbt/kipptaf/models/extracts/focus/`), materializing to the
`kipptaf_extracts` schema. They carry the `stdt_id` / `student_id` null stub
(repointed by [#4205](https://github.com/TEAMSchools/teamster/issues/4205)) and
the crosswalk logic (gaps tracked in
[#4208](https://github.com/TEAMSchools/teamster/issues/4208)).

The **kippmiami** dbt project re-exposes them as thin pass-through models
reading `source("kipptaf_extracts", "rpt_focus__*")` and materializing into
`kippmiami_extracts`. Those pass-throughs exist so a kippmiami-located transport
can read a kippmiami dataset — which is the home #4073 specifies (build in the
kippmiami code location, alongside the existing Focus DLT and Finalsite assets).

Focus imports the five files as one coordinated set keyed on a caller-supplied
`STDT_ID`.

## Decisions

| Decision          | Choice                                                               | Rationale                                                                                                   |
| ----------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Transport         | SFTP (5 coordinated CSVs)                                            | Named scope of #4207; factory exists; #4073 flagged the API may not be able to create the enrollment record |
| Asset location    | `kippmiami` code location, reading `kippmiami_extracts.rpt_focus__*` | Honors #4073; uses the existing pass-through models as designed                                             |
| Asset structure   | Five config-driven factory assets, one daily job                     | Pure reuse of the `build_bigquery_query_sftp_asset` factory; matches the `powerschool` extracts idiom       |
| Cadence           | Daily schedule                                                       | Focus picks up a fresh full set daily; can be scoped to the enrollment window later                         |
| Pre-launch gating | Schedule ships STOPPED (no `default_status`)                         | No query-level gate needed; Ops enables once data and creds are ready                                       |

## Architecture

```text
kipptaf rpt_focus__*          (kipptaf_extracts)   <- #4205 / #4208 land here
  -> kippmiami pass-throughs  (kippmiami_extracts)
  -> 5 build_bigquery_query_sftp_asset definitions  (kippmiami/extracts)
       query -> CSV (Focus header casing via header_replacements)
  -> SFTP push to Focus incoming dir  (SSH_FOCUS resource)
  -> Focus coordinated template import (keyed on STDT_ID)
```

All five assets are built by the existing factory in
`src/teamster/libraries/extracts/assets.py`. No library changes.

## Components

### 1. `SSH_FOCUS` resource

In `src/teamster/core/resources.py`, mirror `SSH_COUCHDROP`:

```python
SSH_FOCUS = SSHResource(
    remote_host=EnvVar("FOCUS_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("FOCUS_SFTP_USERNAME"),
    password=EnvVar("FOCUS_SFTP_PASSWORD"),
)
```

Wire `"ssh_focus": SSH_FOCUS` into the resources dict in
`src/teamster/code_locations/kippmiami/definitions.py`. The factory resolves the
SSH resource key from `destination_config.name` (`focus` -> `ssh_focus`).

`SSHResource` also supports key-based auth — confirm password vs key with
whoever provisions the Focus SFTP account before finalizing the field set.

### 2. `config/focus.yaml`

New file `src/teamster/code_locations/kippmiami/extracts/config/focus.yaml`,
following the shape of `powerschool.yaml`. One `assets:` entry per model:

```yaml
assets:
  - query_config:
      type: schema
      value:
        table:
          schema: kippmiami_extracts
          name: rpt_focus__demographics
    file_config:
      stem: <focus_template_filename>
      suffix: csv
      format:
        header_replacements:
          stdt_id: <FOCUS_HEADER>
          # ... lowercase dbt column -> Focus header casing
    destination_config:
      name: focus
      path: <focus_incoming_dir>
  # ... four more entries: student_enrollment, addresses, contacts,
  #     linked_students
```

`header_replacements` is a pure rename of the CSV header row (no reordering or
filtering). dbt columns are lowercase `snake_case`; Focus headers follow the
template's casing.

### 3. `assets.py`

In `src/teamster/code_locations/kippmiami/extracts/assets.py`, add the focus
asset list and append it to `assets`:

```python
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

### 4. `jobs.py`

```python
focus_extract_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}__extracts__focus__asset_job",
    selection=focus_extract_assets,
)
```

### 5. `schedules.py`

```python
focus_extract_assets_schedule = ScheduleDefinition(
    job=focus_extract_asset_job,
    cron_schedule="0 3 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)
```

Add to the `schedules` list. No `default_status` is set, so Dagster ships the
schedule STOPPED. Asset keys land as `kippmiami/extracts/focus/*`.

## Data flow

1. Upstream dbt builds `kipptaf_extracts.rpt_focus__*`, then the kippmiami
   pass-throughs into `kippmiami_extracts.rpt_focus__*`.
2. The daily job materializes the five focus extract assets together.
3. Each asset runs its BigQuery query, serializes to CSV applying
   `header_replacements`, and uploads to the Focus incoming directory.
4. Focus imports the coordinated set, keyed on `STDT_ID`.

## Error handling and edge cases

- **Empty-result guard** — the factory returns early when the query yields zero
  rows, so no empty CSV is written or uploaded.
- **Non-atomic five-file delivery** — the five SFTP uploads are independent; a
  mid-run failure could leave a partial set on the server. Mitigated by fixed
  filenames that overwrite on the next daily run, and by the schedule staying
  stopped until the data is real. Revisit a single all-or-nothing asset only if
  Focus chokes on a partial set.
- **Stopped schedule is the launch gate** — Ops enables the schedule only once
  all of these hold: `STDT_ID` populated (#4205), the E05/E02 enrollment-code
  rule resolved (#4208), and Focus SFTP credentials provisioned.

## Testing and validation

- `uv run dbt build --select rpt_focus__*` in both kipptaf and kippmiami —
  models build.
- `uv run python -c "import teamster.code_locations.kippmiami.definitions"` and
  `uv run dagster definitions validate -m teamster.code_locations.kippmiami.definitions`
  — wiring imports and validates (env-var false errors in codespace are
  expected; fall back to the import check).
- Diff a generated CSV header row against the Focus template spreadsheet to
  confirm casing.
- Optional: a single-asset run in a branch deployment against a Focus **test**
  SFTP path once credentials exist.

## Dependencies and ship gates

These gate **enabling** the schedule, not building the transport:

- [#4205](https://github.com/TEAMSchools/teamster/issues/4205) — `STDT_ID`
  populated (blocked on Finalsite minting the Focus student id).
- [#4208](https://github.com/TEAMSchools/teamster/issues/4208) §1 — E05 vs E02
  enrollment-code rule resolved. §2 (unfilled crosswalk cells) is warn-level and
  does not block.

## Out of scope

- OAuth2 Focus API transport (the swappable alternative; deferred).
- The #4205 / #4208 upstream dbt fixes.
- The #4073 reconciliation model and the optional Finalsite write-back.

## Open items to confirm (not blocking the build)

- Exact Focus header strings and filenames, from the Focus SFTP template
  spreadsheet — feed `header_replacements` and each `stem`.
- Focus SFTP host, credentials, incoming path, and auth method (password vs key)
  — Ops/IT provision in Dagster Cloud.
- Focus incoming-directory path convention (relative preferred, per the extracts
  library guidance).
