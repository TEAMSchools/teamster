# CLAUDE.md — `src/teamster/`

## Overview

```text
teamster/
  __init__.py             # GCS_PROJECT_NAME = "teamster-332318"
  core/                   # Shared infrastructure (IO managers, resources, utils)
  libraries/              # Reusable asset builders, resources, and schemas
  code_locations/         # Per-district Dagster definitions (kipptaf, kippnewark, etc.)
```

## Library + Code Location Pattern

Integrations follow a two-layer separation:

1. **`libraries/<integration>/`** — reusable factory functions, resource
   classes, Avro schemas, and sensors. Never import from a code location.
2. **`code_locations/<district>/<integration>/`** — calls the library factory
   with district-specific YAML config via `config_from_files()`. Wires assets
   into the code location's `definitions.py`.

This means adding a new district to an existing integration requires only YAML
config and a few lines of Python in the code location — no library changes.

## Python Standards

`requires-python = ">=3.13"`. All library resource methods require return type
annotations. Use built-in generics (`list[str]`, `dict[str, int]`), `X | None`
for nullable params, and `_` for unused unpacked variables. Callable-returning
functions annotate as `Callable[[], ReturnType]` (import from
`collections.abc`).

**`defaultdict` typing**: `defaultdict(set[T])` works at runtime in 3.13
(GenericAlias is callable) but is semantically wrong — use
`defaultdict[K, set[T]](set)` with the subscript on the type annotation, not the
factory argument.

**Inline type parameters** (PEP 695): Prefer `def foo[T](x: T) -> T` over
`TypeVar`. The formatter removes unused `TypeVar` imports before the binding is
defined, causing unresolved name errors.

**kwargs forwarding**: When extracting a kwarg default before spreading
`**kwargs`, always use `pop`, never `get` — `get` leaves the key in `kwargs`,
causing `TypeError: got multiple values for keyword argument` if the caller
passed it. `chunk()` from `core/utils/functions` returns `Iterator[list]`, not
`list` — wrap in `list()` if `len()` or multiple passes are needed.

**Docstrings**: Follow the
[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
API reference URLs go in the extended description, never the summary line.
Multi-line docstrings are permitted under Google style — this overrides Claude's
default "one short line max" rule.

`ScheduleEvaluationContext.log` and `SensorEvaluationContext.log` return
`logging.Logger`; `AssetExecutionContext.log` returns `DagsterLogManager`. Use
`logging.Logger` when a function accepts log from any context.

**Runtime type narrowing**: Use `check.is_tuple()`, `check.inst()`,
`check.not_none()` from `dagster_shared` — never `assert isinstance(...)`
(`assert` is stripped by `-O`).

## Library Categories

Libraries fall into four patterns based on how they ingest data:

| Pattern            | Libraries                                                                                  | How it works                                                    |
| ------------------ | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| **SFTP file drop** | collegeboard, edplan, fldoe, iready, nsc, pearson, performance_management, renlearn, titan | `build_sftp_*_asset()` from `libraries/sftp/` + Avro schemas    |
| **REST API**       | coupa, deanslist, knowbe4, level_data, overgrad, smartrecruiters                           | Custom `build_*_asset()` factory + resource class               |
| **Framework**      | dbt, dlt, google, airbyte, fivetran                                                        | Dagster-native integration (`dagster-dbt`, `dagster-dlt`, etc.) |
| **Multi-access**   | adp (API + SFTP), amplify (API + SFTP), powerschool (ODBC + SFTP + API)                    | Multiple factories per product line                             |

Schema-only libraries (collegeboard, dayforce, fldoe, nsc, pearson,
performance_management) contain only Avro schemas — the asset is built in the
code location using the generic SFTP factory.

## Code Location Structure

`kippnewark` is the most complete district code location — it uses every
available integration. Use it as the reference implementation when adding new
integrations to other districts.

Each code location follows the same layout:

```text
code_locations/<name>/
  CLAUDE.md          # Module-specific context (read before working here)
  __init__.py        # CODE_LOCATION, LOCAL_TIMEZONE, CURRENT_FISCAL_YEAR, DBT_PROJECT
  definitions.py     # Dagster Definitions object wiring everything together
  resources.py       # Location-specific resource instances (if any)
  dbt/assets.py      # dbt asset definitions
  <integration>/     # Per-integration assets, config YAML, optional sensors
```

**Identity constants** (defined in `__init__.py`):

| Constant              | Example (`kippnewark`)          |
| --------------------- | ------------------------------- |
| `CODE_LOCATION`       | `"kippnewark"`                  |
| `LOCAL_TIMEZONE`      | `ZoneInfo("America/New_York")`  |
| `CURRENT_FISCAL_YEAR` | fiscal year (updated each July) |

**GCS bucket**: `teamster-<code_location>` (redirects to `teamster-test` in
branch deployments).

## Resource Model

Resources are defined in two places:

- **`core/resources.py`** — shared singletons (BigQuery, GCS, DLT, Google
  Workspace, SFTP/SSH clients) and factories (IO managers, dbt CLI, PowerSchool
  SSH). Imported by every code location.
- **`code_locations/<name>/resources.py`** — location-specific resources (e.g.,
  kipptaf defines ADP WFN, Airbyte, Coupa, LDAP, Tableau, etc.). Only exists
  when a code location needs resources beyond the shared set.

## Asset Key Convention

`[code_location, integration, ...]` — e.g., `kippnewark/powerschool/students`,
`kipptaf/extracts/tableau/attendance_dashboard`.

## Automation Conditions

See `core/CLAUDE.md` for automation condition builders
(`dbt_view_automation_condition`, `dbt_union_relations_automation_condition`,
`dbt_table_automation_condition`). Non-dbt assets use
`AutomationCondition.eager()` or sensor/schedule triggers.

## IO Managers

See `core/CLAUDE.md` for IO manager details (three modes: default, avro, file).
All use Hive-style partitioned GCS paths.

## Common Patterns

**Avro schema validation**: All asset factories yielding Avro output call
`build_check_spec_avro_schema_valid()` + `check_avro_schema_valid()` from
`core/asset_checks.py` (warns on extra fields, doesn't fail).

**Partition key substitution**: SFTP assets use regex named groups in
`remote_dir_regex`/`remote_file_regex`. At runtime, named groups are replaced
with partition dimension values via `regex_pattern_replace()`.

**SFTP sensors**: List remote directories, match files against asset regexes,
extract partition keys from named groups, emit `RunRequest`s grouped by
`(job_name, partition_key)`. Sensor cursors should store max file mtime from
matched files, not `now.timestamp()` — wall-clock cursors skip files with older
mtimes. `listdir_attr_r`'s `dir_mtimes` subtree-prune is only sound when the
SFTP server advances parent-dir mtime on entry changes — Amplify mClass does
not. Before opting a new sensor into `dir_mtimes=`, verify with
`dir.st_mtime >= max(child.st_mtime)` across the watched tree.

**Fiscal year**: July 1 start. `FiscalYear` class and
`FiscalYearPartitionsDefinition` in `core/utils/classes.py`.

**Retry pattern**: Use `tenacity` — standard import set:
`retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter`.
Match on a specific exception class (define one if the upstream code raises bare
`Exception`), never on error message or bare `Exception`. Existing examples:
`libraries/adp/workforce_now/api/resources.py`,
`libraries/tableau/resources.py`, `libraries/level_data/grow/resources.py`. Wrap
the init path (`fetch_token` / `connect` in `setup_for_execution`) too, not just
the request method. For network-call retries, the predicate must include
`(RequestsConnectionError, Timeout, HTTPError)` — `HTTPError` alone misses
`ConnectTimeout`. For runtime-parameterized retry loops (e.g.
`with_powerschool_retry`), use `tenacity.Retrying` — a manual
`for attempt in range(...)` has no backoff. Avoid broad base classes whose
subclasses include deterministic config errors (e.g.
`paramiko.ssh_exception.SSHException` covers `IncompatiblePeer`,
`BadHostKeyException`, `BadAuthenticationType`). List transient subclasses
explicitly.

**Don't `log.exception` inside retry-wrapped helpers**. GCP Error Reporting
files groups at ERROR severity, so logging a traceback inside a context manager
/ helper that's called from a retry loop creates false-positive error groups for
transient failures the retry layer recovers from. Let the retry wrapper log
intermediate attempts at WARNING; Dagster logs unrecovered failures at the run
level.

## Development Commands

```bash
# Start Dagster webserver locally (all code locations)
uv run dagster dev

# Validate Dagster definitions for a code location
uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions

# Prepare and package a dbt project (required before running dbt assets)
uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/kipptaf/__init__.py
```

`dagster definitions validate` may mislead locally — env vars unavailable in
codespace cause false errors unrelated to production failures. Fall back to
`uv run python -c "import <module>"` for syntactic checks when validate fails on
missing manifest or env vars.
