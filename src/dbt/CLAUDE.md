# CLAUDE.md — `src/dbt/`

## Overview

Three tiers, told apart by name (`ls src/dbt` for the current list):

- **Source-system** (everything not `kipp*`) — clean and contract-enforce raw
  data from one source system.
- **District-specific** (`kippnewark`, `kippcamden`, `kippmiami`,
  `kipppaterson`) — combine source packages for a single district.
- **Network analytics** (`kipptaf`) — cross-district marts, reporting, and
  extracts for the network.

## Project Dependency Map

Not every district uses every source package. See each district project's
CLAUDE.md for its active packages.

Authoritative consumer list for a source-system package:
`grep -l 'local: ../<pkg>' src/dbt/*/packages.yml`. The district "Active Source
Packages" prose drifts; `packages.yml` is ground truth. `kipptaf` consumes most
source data via `source()`, not as a package.

**A model name can exist in both a source-system package and `kipptaf`** (e.g.
`int_finalsite__student_contacts`). `ref()` resolves to the CURRENT project's
copy, so when reading a `kipptaf` model's upstream, open the `kipptaf` file —
the same-named package file is a different model. Confirm with
`find src/dbt -name '<model>.sql'` before reading.

## District Variables

Each project's `vars:` block is the top of its `dbt_project.yml` — read it
there; source-system projects declare null/zero defaults that consuming
districts override. `current_academic_year` / `current_fiscal_year` roll over
each July.

Not visible in the yml: `cloud_storage_uri_base` redirects to
`gs://teamster-test/dagster/<project>` when
`DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT=1`, via an inline conditional in each
`external.location` template.

## Source-package staging builds in every consuming district

A source-system package's staging models build in **every** district that
imports it, but only carry data where that source's Dagster ingestion is wired
per code location — e.g. while finalsite `contacts` ingestion was Miami-only,
`stg_finalsite__contacts` still built in all four districts (all import the
`finalsite` package) but carried rows only in `kippmiami`; the contacts asset is
now wired in all four regions. Before promoting a district model to a shared
source package, confirm the source ingestion exists in every consuming district,
or the promoted model builds empty there (or fails on a missing external).

**Partial-endpoint onboarding**: when a district ingests only a subset of a
source package's endpoints, disable BOTH the unused `stg_*` models AND their
`src_*` sources in the district `dbt_project.yml`. An enabled staging model over
a disabled source is a parse error, and `stage_external_sources` fails creating
an AVRO external over an empty GCS prefix (autodetect needs >=1 file). Don't
copy a peer district's disable list blindly — a district that _once_ pulled an
endpoint keeps stale Avro so its source still stages (e.g. Newark deanslist
leaves `homework`/`lists`/`dff_stats` enabled), but a never-pulled district must
disable them.

To gate an _optional_ package layer per region, split the package into
method/source subfolders (`api/`, `sftp/` — the amplify convention) and set
`<package>: <method>: +enabled: false` in the unwired district's
`dbt_project.yml`. Keep network-wide feeds enabled everywhere (e.g. finalsite
SFTP `status_report` is consumed by kipptaf in all regions; only `api` is
Miami-only). Method subfolders don't change asset keys.

**Merging `dbt_project.yml` package configs can silently duplicate a top-level
key.** When two branches each add `models: <package>:` (or `sources:`) at
different positions, git's line-merge keeps BOTH with no conflict marker (later
wins; may be invalid YAML). After merging a `dbt_project.yml`, grep for
duplicate package keys and consolidate.

## Shipped Profiles (`src/dbt/*/profiles.yml`)

Dagster-only: default target `prod` + `defer` output. Branch deployments
explicitly pass `target="defer"` via `DbtCliResource`; prod uses the profile
default (no Python override needed). No `GITHUB_USER` — not available in Dagster
deployments. Developers use `<repo-root>/.dbt/profiles.yml` (not
`~/.dbt/profiles.yml`) for full target support.

- **`job_retries`**: dbt-bigquery defaults to `1`, which doesn't absorb
  sustained transient 503s on `client.list_datasets()` at adapter init. Set
  `job_retries: 3` on the `prod` output. Set on all district profiles and
  kipptaf.
- **`job_retries` fires on 7 reasons only**: `rateLimitExceeded`,
  `backendError`, `internalError`, `badGateway` (`_RETRYABLE_REASONS`) plus
  `jobBackendError`, `jobInternalError`, `jobRateLimitExceeded`
  (`job_retry_reasons`), per `_job_should_retry` in
  `google/cloud/bigquery/retry.py`. Every other reason — `notFound`,
  `resourcesExceeded`, `invalidQuery` — fails on attempt 1 at any `job_retries`
  value, so never propose raising it for those.
- **`job_execution_timeout_seconds`**: Set to `900` on the `prod` output of all
  five kipp\* profiles. Caps each BigQuery job server-side (`job_timeout_ms`) so
  a runaway single model is cancelled by BigQuery before Dagster's run-level
  `max_runtime` (1800s). Without it, a killed dbt run leaves the in-flight BQ
  job orphaned — dbt does NOT cancel on termination (upstream limitation,
  dbt-core #5275/#9639) — and the zombie `create or replace` can overwrite a
  successful auto-retry's output with staler data. Routine models run <=330s
  network-wide (affected models' p99 <=78s), so 900s won't false-kill legit
  work.
- A dbt **`409 Already Exists: Job <id>`** failure is a `job_retries` collision
  (the original submit succeeded server-side but the response was lost; the
  retry re-sends the same job_id). The job usually **succeeded** — confirm via
  `JOBS_BY_PROJECT` (`state=DONE`, `error_result IS NULL`) before treating it as
  real. The Dagster run-retry absorbs it.

## Model Conventions

Conventions apply to **every** dbt project in this directory and load as
path-scoped rules on the first read of a matching file:

- `.claude/rules/dbt-sql.md` (`*.sql`): SQL conventions, column ordering, row
  picking and surrogate keys, date-range joins, formatting.
- `.claude/rules/dbt-yaml.md` (`*.yml`): properties, sources, external tables,
  test config, unit-test fixtures, YAML conventions.
- `.claude/rules/dbt-models.md` (`models/**`, `tests/**`): per-layer
  requirements, moving and retiring models, materialization changes,
  cross-project column changes.

Bash-driven work has no file to trigger on, so invoke the skill instead:
`dbt-local-dev` for local builds, `--defer`, `dbt clone`, and stale-dev traps;
`pr-ci-review` for dbt Cloud CI selection and state comparison.
