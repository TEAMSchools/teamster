# Finalsite Incremental Contacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull only Finalsite contacts changed since the previous day,
accumulate them as Hive-partitioned Avro, and dedupe to one row per contact in
staging, so the pull runs twice daily instead of once and lands before the
consumers that read it.

**Architecture:** The contacts asset gains a `DailyPartitionsDefinition` and
derives the API's `since` parameter from its own partition key
(`partition_date - 1`), so the partition key IS the watermark and no cursor is
stored. Each pull writes its own Hive partition instead of replacing one object;
`stg_finalsite__contacts` picks the newest partition per contact `id` with
`dbt_utils.deduplicate`, and `stg_finalsite__contact_relationships` reads that
deduped model rather than the raw source.

**Tech Stack:** Dagster (assets, `DailyPartitionsDefinition`, `@schedule`), dbt
on BigQuery (external Avro source, `dbt_utils.deduplicate`, unit tests), `uv`
for all Python execution.

**Design spec:**
`docs/superpowers/specs/2026-08-10-finalsite-incremental-contacts-design.md`

## Global Constraints

- **Worktree:** all work happens in
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts`.
  Use `git -C <worktree>` on every git call and
  `--project-dir <worktree>/src/dbt/<project>` on every dbt call. Editing
  `/workspaces/teamster/<path>` silently dirties `main`.
- **The asset key must not change:** `[{code_location}, finalsite, contacts]`.
- **The dbt source name must not change:** `source('finalsite', 'contacts')`.
- **Schedule names must stay byte-identical** to today's
  (`{code_location}__finalsite__contacts__daily_asset_job_schedule`). Renaming
  mints a new Dagster+ schedule object and abandons its status and tick history.
- **No `QUALIFY`, no dup-masking `SELECT DISTINCT`.** Use
  `dbt_utils.deduplicate`. Its `order_by` must use bare `desc` — BigQuery
  rejects explicit null-ordering inside the `array_agg` the macro compiles to.
- **The `finalsite_api` pool stays at limit 1.** #4408 is out of scope.
- **Python:** always `uv run`, never bare `python`. Return type annotations on
  all library functions. Built-in generics (`list[str]`, `dict[str, int]`),
  `X | None` for nullable.
- **Never run `trunk fmt` or `trunk check` manually** except the explicit
  `--force` verification steps in this plan, which run from inside the worktree
  using the absolute binary `/workspaces/teamster/.trunk/tools/trunk`.
- **Markdown:** every fenced block needs a language (MD040).
- **`CUTOVER_START_DATE` is `2026-08-11`.** If the merge slips past that date,
  bump it before merging. A `start_date` in the past only shows extra missing
  partitions, which is harmless, so erring early is safe.

---

### Task 1: Derive `since` from the partition key in the asset factory

**Files:**

- Modify: `src/teamster/libraries/finalsite/api/assets.py`
- Test: `tests/libraries/test_finalsite_contacts_since.py` (create)

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces:
  - `get_finalsite_since(partition_key: str) -> str` — returns the ISO date one
    day before `partition_key`.
  - `FinalsiteContactsConfig` — a `dagster.Config` subclass with one field,
    `full_pull: bool = False`.
  - `build_finalsite_asset(code_location: str, asset_name: str, schema, params: dict | None = None, partitions_def=None)`
    — the existing factory plus a trailing optional `partitions_def`.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/test_finalsite_contacts_since.py`:

```python
from teamster.libraries.finalsite.api.assets import get_finalsite_since


def test_since_subtracts_the_safety_day():
    assert get_finalsite_since("2026-08-11") == "2026-08-10"


def test_since_crosses_a_month_boundary():
    assert get_finalsite_since("2026-08-01") == "2026-07-31"


def test_since_crosses_a_year_boundary():
    assert get_finalsite_since("2026-01-01") == "2025-12-31"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts \
  && uv run pytest tests/libraries/test_finalsite_contacts_since.py -v
```

Expected: FAIL with `ImportError: cannot import name 'get_finalsite_since'`.

- [ ] **Step 3: Add the helper and the config class**

In `src/teamster/libraries/finalsite/api/assets.py`, replace the import block
and add the two new definitions above `build_finalsite_asset`:

```python
from datetime import date, timedelta

from dagster import AssetExecutionContext, Config, Output, asset

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.finalsite.api.resources import FinalsiteResource


def get_finalsite_since(partition_key: str) -> str:
    """Return the `since` date for a pull, one day before the partition date.

    The API's `since` is date-grained, so the finest possible increment is one
    day. Subtracting a safety day means a run that straddles midnight or hits a
    vendor clock skew cannot drop records, and it makes every pull on a given
    date a superset of any earlier pull on that date — which is what lets the
    midday run overwrite the overnight run's partition safely. Measured cost on
    kippmiami: 43 extra records, 2 extra pages.
    """
    return (date.fromisoformat(partition_key) - timedelta(days=1)).isoformat()


class FinalsiteContactsConfig(Config):
    """Run config for a contacts pull.

    `full_pull` omits `since` entirely, pulling every contact. Used once per
    district to seed the first partition; a `since` pull alone would leave
    staging holding only contacts that changed after go-live.
    """

    full_pull: bool = False
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts \
  && uv run pytest tests/libraries/test_finalsite_contacts_since.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Wire the factory to use them**

Replace the body of `build_finalsite_asset` in the same file:

```python
def build_finalsite_asset(
    code_location: str,
    asset_name: str,
    schema,
    params: dict | None = None,
    partitions_def=None,
):
    key = [code_location, "finalsite", asset_name]

    @asset(
        key=key,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        check_specs=[build_check_spec_avro_schema_valid(key)],
        group_name="finalsite",
        # One shared pool across ALL districts (not per-location): the Finalsite
        # gateway throttles by source IP, so simultaneous pulls from the shared
        # egress IP return 403 even with separate subdomains and credentials.
        # Set this pool's limit to 1 in Dagster+ to serialize them. See #4408.
        pool="finalsite_api",
        kinds={"python"},
    )
    def _asset(
        context: AssetExecutionContext,
        finalsite: FinalsiteResource,
        config: FinalsiteContactsConfig,
    ):
        request_params = {**(params or {})}

        # A partitioned asset pulls incrementally: the partition key IS the
        # watermark, so a failed run writes no partition and advances nothing.
        # `full_pull` is the seed escape hatch.
        if partitions_def is not None and not config.full_pull:
            request_params["since"] = get_finalsite_since(context.partition_key)

        data = finalsite.list(path=asset_name, params=request_params)

        yield Output(
            value=(data, schema),
            metadata={
                "record_count": len(data),
                "since": request_params.get("since", "FULL PULL"),
            },
        )
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
```

`partitions_def=None` keeps the factory usable for a future non-partitioned
asset, and the `since` derivation is gated on it rather than assumed.

- [ ] **Step 6: Verify the module still imports**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts \
  && uv run python -c "from teamster.libraries.finalsite.api.assets import build_finalsite_asset, get_finalsite_since, FinalsiteContactsConfig; print('ok')"
```

Expected: `ok`.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts add \
  src/teamster/libraries/finalsite/api/assets.py \
  tests/libraries/test_finalsite_contacts_since.py
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts commit -m "feat(finalsite): derive an incremental since date from the partition key

Refs #4715"
```

---

### Task 2: Pass `partitions_def` at the four code-location call sites

**Files:**

- Modify: `src/teamster/code_locations/kippnewark/finalsite/assets.py:25-30`
- Modify: `src/teamster/code_locations/kippcamden/finalsite/assets.py:27-32`
- Modify: `src/teamster/code_locations/kippmiami/finalsite/assets.py:27-32`
- Modify: `src/teamster/code_locations/kipppaterson/finalsite/assets.py:27-32`

**Interfaces:**

- Consumes: `build_finalsite_asset(..., partitions_def=...)` from Task 1.
- Produces: four partitioned `contacts` assets, still keyed
  `[{code_location}, finalsite, contacts]`.

- [ ] **Step 1: Edit all four call sites**

In each of the four files, add the two imports and the `partitions_def`
argument. The `contacts` block becomes identical in all four (only
`CODE_LOCATION` and the already-imported `LOCAL_TIMEZONE` differ by module):

```python
from dagster import DailyPartitionsDefinition

from teamster.code_locations.<location> import CODE_LOCATION, LOCAL_TIMEZONE

contacts = build_finalsite_asset(
    code_location=CODE_LOCATION,
    asset_name="contacts",
    schema=CONTACTS_SCHEMA,
    params={"includes": "contacts.relationships"},
    # One partition per pull date. The partition key is the incremental
    # watermark (see get_finalsite_since); start_date is the cutover date, so
    # Dagster shows no backlog of partitions that predate the migration.
    partitions_def=DailyPartitionsDefinition(
        start_date="2026-08-11", timezone=str(LOCAL_TIMEZONE)
    ),
)
```

Note on each file: `kippnewark` already imports `CURRENT_FISCAL_YEAR` and
`LOCAL_TIMEZONE` may not be imported yet — add it to the existing
`from teamster.code_locations.<location> import ...` line rather than adding a
second import statement.

`params` keeps only `includes`. Do **not** add `since_includes_expanded`: it
measured as a no-op (identical id sets with it on and off), and the relationship
edits it would catch arrive anyway.

- [ ] **Step 2: Verify each module imports and the asset is partitioned**

`kippnewark` and `kippcamden` import cleanly. `kippmiami` and `kipptaf`
`definitions` modules fail at module load in a codespace on unrelated dlt
credential specs, so import the `finalsite` submodule alone for those.

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts \
  && uv run python -c "
from dagster import DailyPartitionsDefinition
for loc in ['kippnewark', 'kippcamden', 'kippmiami', 'kipppaterson']:
    mod = __import__(f'teamster.code_locations.{loc}.finalsite.assets', fromlist=['contacts'])
    pd = mod.contacts.partitions_def
    assert isinstance(pd, DailyPartitionsDefinition), (loc, pd)
    assert mod.contacts.key.to_user_string() == f'{loc}/finalsite/contacts', mod.contacts.key
    print(loc, 'ok', pd)
"
```

Expected: four `ok` lines, each naming a `DailyPartitionsDefinition`.

Use `key.to_user_string()` for the slash form — `str(AssetKey([...]))` returns
the repr, not `code_location/integration/name`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts add \
  src/teamster/code_locations/kippnewark/finalsite/assets.py \
  src/teamster/code_locations/kippcamden/finalsite/assets.py \
  src/teamster/code_locations/kippmiami/finalsite/assets.py \
  src/teamster/code_locations/kipppaterson/finalsite/assets.py
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts commit -m "feat(finalsite): partition the contacts asset by pull date

Refs #4715"
```

---

### Task 3: Schedule factory at 00:15 and 12:00 for all four districts

**Files:**

- Create: `src/teamster/libraries/finalsite/api/schedules.py`
- Modify: `src/teamster/code_locations/kippnewark/finalsite/schedules.py`
- Modify: `src/teamster/code_locations/kippcamden/finalsite/schedules.py`
- Modify: `src/teamster/code_locations/kippmiami/finalsite/schedules.py`
- Modify: `src/teamster/code_locations/kipppaterson/finalsite/schedules.py`
- Test: `tests/libraries/test_finalsite_contacts_schedule.py` (create)

**Interfaces:**

- Consumes: the partitioned `contacts` assets from Task 2.
- Produces:
  `build_finalsite_contacts_schedule(code_location: str, execution_timezone: str, asset_selection: list[AssetsDefinition], cron_schedule: Sequence[str] = ("15 0 * * *", "0 12 * * *"), max_runtime_seconds: int = 900) -> ScheduleDefinition`

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/test_finalsite_contacts_schedule.py`. It builds its own
fixture asset rather than importing a code location, so it needs no dbt
manifest:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from dagster import (
    DailyPartitionsDefinition,
    DagsterInstance,
    asset,
    build_schedule_context,
)

from teamster.libraries.finalsite.api.schedules import (
    build_finalsite_contacts_schedule,
)

TIMEZONE = "America/New_York"


@asset(
    key=["test", "finalsite", "contacts"],
    partitions_def=DailyPartitionsDefinition(
        start_date="2026-08-01", timezone=TIMEZONE
    ),
)
def _contacts() -> None: ...


def _run_requests_at(hour: int, minute: int):
    schedule = build_finalsite_contacts_schedule(
        code_location="test",
        execution_timezone=TIMEZONE,
        asset_selection=[_contacts],
    )

    context = build_schedule_context(
        instance=DagsterInstance.ephemeral(),
        scheduled_execution_time=datetime(
            2026, 8, 11, hour, minute, tzinfo=ZoneInfo(TIMEZONE)
        ),
    )

    return list(schedule.evaluate_tick(context).run_requests or [])


def test_overnight_tick_targets_todays_partition():
    run_requests = _run_requests_at(hour=0, minute=15)

    assert len(run_requests) == 1
    assert run_requests[0].partition_key == "2026-08-11"


def test_midday_tick_targets_the_same_partition():
    run_requests = _run_requests_at(hour=12, minute=0)

    assert len(run_requests) == 1
    assert run_requests[0].partition_key == "2026-08-11"


def test_run_key_is_none_so_the_second_daily_tick_is_not_deduplicated():
    # Both ticks target the same partition key. A run_key equal to the partition
    # key would make Dagster's idempotency silently swallow the 12:00 run.
    assert _run_requests_at(hour=0, minute=15)[0].run_key is None


def test_max_runtime_tag_is_bounded_for_an_incremental_pull():
    tags = _run_requests_at(hour=0, minute=15)[0].tags

    assert tags["dagster/max_runtime"] == "900"


def test_schedule_name_matches_the_existing_dagster_plus_object():
    schedule = build_finalsite_contacts_schedule(
        code_location="test",
        execution_timezone=TIMEZONE,
        asset_selection=[_contacts],
    )

    assert schedule.name == "test__finalsite__contacts__daily_asset_job_schedule"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts \
  && uv run pytest tests/libraries/test_finalsite_contacts_schedule.py -v
```

Expected: FAIL with
`ModuleNotFoundError: No module named 'teamster.libraries.finalsite.api.schedules'`.

- [ ] **Step 3: Write the schedule factory**

Create `src/teamster/libraries/finalsite/api/schedules.py`:

```python
from collections.abc import Sequence

from dagster import (
    MAX_RUNTIME_SECONDS_TAG,
    AssetsDefinition,
    RunRequest,
    ScheduleDefinition,
    ScheduleEvaluationContext,
    schedule,
)


def build_finalsite_contacts_schedule(
    code_location: str,
    execution_timezone: str,
    asset_selection: list[AssetsDefinition],
    cron_schedule: Sequence[str] = ("15 0 * * *", "0 12 * * *"),
    max_runtime_seconds: int = 900,
) -> ScheduleDefinition:
    """Build the twice-daily incremental contacts schedule for one district.

    Both ticks target the SAME daily partition: 00:15 lands before the 01:00
    Google Directory account sync and the 01:25 DeansList ship, and 12:00 feeds
    the midday Focus import cycle. Neither is top-of-hour, where GKE Autopilot
    fan-out adds 3-9 minutes of step-pod scheduling wait.

    The name is deliberately unchanged from the pre-incremental schedule --
    renaming mints a NEW Dagster+ schedule object and abandons this one's status
    and tick history -- so "daily" now means twice a day.
    """

    @schedule(
        name=f"{code_location}__finalsite__contacts__daily_asset_job_schedule",
        cron_schedule=list(cron_schedule),
        execution_timezone=execution_timezone,
        target=asset_selection,
    )
    def _schedule(context: ScheduleEvaluationContext):
        # run_key stays None: both daily ticks share a partition key, and a
        # run_key equal to it would dedupe the second run away.
        yield RunRequest(
            partition_key=context.scheduled_execution_time.date().isoformat(),
            tags={MAX_RUNTIME_SECONDS_TAG: str(max_runtime_seconds)},
        )

    return _schedule
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts \
  && uv run pytest tests/libraries/test_finalsite_contacts_schedule.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Replace each district's schedule module**

`src/teamster/code_locations/kippnewark/finalsite/schedules.py` becomes (and the
other three are identical apart from the import path):

```python
from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.finalsite.assets import contacts
from teamster.libraries.finalsite.api.schedules import (
    build_finalsite_contacts_schedule,
)

finalsite_contacts_daily_asset_job_schedule = build_finalsite_contacts_schedule(
    code_location=CODE_LOCATION,
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=[contacts],
)

schedules = [
    finalsite_contacts_daily_asset_job_schedule,
]
```

For `kippmiami`, this replaces the `["0 4 * * *", "0 12 * * *"]` cron. Preserve
the substance of its existing comment by moving the midday-chain rationale into
the call site:

```python
finalsite_contacts_daily_asset_job_schedule = build_finalsite_contacts_schedule(
    code_location=CODE_LOCATION,
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=[contacts],
    # 12:00 feeds the midday Focus import cycle, firing alongside the Focus dlt
    # pull rather than staggered behind it: they share no pool and neither gates
    # the other. The 12:45 delivery is a plain cron with a 45-minute time
    # budget, not a dependency -- an incremental pull uses ~1-2 min of it where
    # the full snapshot used ~5. 00:15 replaces the old 04:00: FRESH's 05:00
    # Tableau extract still reads a same-day pull, and the NJ consumers at 01:00
    # and 01:25 stop reading yesterday's. See #4715.
)
```

- [ ] **Step 6: Verify the schedules resolve**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts \
  && uv run python -c "
for loc in ['kippnewark', 'kippcamden', 'kippmiami', 'kipppaterson']:
    mod = __import__(f'teamster.code_locations.{loc}.finalsite.schedules', fromlist=['schedules'])
    s = mod.schedules[0]
    assert s.name == f'{loc}__finalsite__contacts__daily_asset_job_schedule', s.name
    print(s.name, s.cron_schedule)
"
```

Expected: four lines, each with the unchanged name and
`['15 0 * * *', '0 12 * * *']`.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts add \
  src/teamster/libraries/finalsite/api/schedules.py \
  tests/libraries/test_finalsite_contacts_schedule.py \
  src/teamster/code_locations/kippnewark/finalsite/schedules.py \
  src/teamster/code_locations/kippcamden/finalsite/schedules.py \
  src/teamster/code_locations/kippmiami/finalsite/schedules.py \
  src/teamster/code_locations/kipppaterson/finalsite/schedules.py
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts commit -m "feat(finalsite): pull contacts at 00:15 and 12:00 on a shared schedule factory

The NJ consumers of stg_finalsite__contacts run at 01:00 (Google Directory
user sync), 01:25 (DeansList) and 18:00 (ParentSquare), all ahead of the
04:00 pull that fed them, so they shipped day-old contacts. 00:15 puts the
pull in front of them. Drops max_runtime from 3600s to 900s.

Refs #4715"
```

---

### Task 4: Hive-partition the dbt external source

**Files:**

- Modify: `src/dbt/finalsite/models/sources-external.yml:28-40`

**Interfaces:**

- Consumes: the partitioned GCS layout written by Task 2's asset.
- Produces: `source('finalsite', 'contacts')` exposing `_dagster_partition_date`
  as a column, which Task 5 orders on.

- [ ] **Step 1: Add `hive_partition_uri_prefix` to the contacts source**

The `contacts` entry becomes (mirroring `status_report` twelve lines above it,
which already uses this pattern):

```yaml
- name: contacts
  external:
    location: "{{ var('cloud_storage_uri_base') }}/finalsite/contacts/*"
    options:
      connection_name: "{{ var('bigquery_external_connection_name') }}"
      metadata_cache_mode: MANUAL
      max_staleness: INTERVAL 7 DAY
      hive_partition_uri_prefix:
        "{{ var('cloud_storage_uri_base',
        env_var('DBT_DEV_CLOUD_STORAGE_URI_BASE', '')) }}/finalsite/contacts/"
      format: AVRO
      enable_logical_types: true
  config:
    meta:
      dagster:
        asset_key:
          - "{{ project_name }}"
          - finalsite
          - contacts
```

`location` is unchanged. Only `hive_partition_uri_prefix` is added.

- [ ] **Step 2: Verify the project still parses**

Run:

```bash
cd /workspaces/teamster \
  && uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts/src/dbt/kippnewark
```

Expected: parse succeeds with no error mentioning `sources-external.yml`.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts add \
  src/dbt/finalsite/models/sources-external.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts commit -m "feat(finalsite): hive-partition the contacts external source

Refs #4715"
```

---

### Task 5: Dedupe to one row per contact in `stg_finalsite__contacts`

**Files:**

- Modify: `src/dbt/finalsite/models/api/staging/stg_finalsite__contacts.sql`
- Modify:
  `src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contacts.yml`

**Interfaces:**

- Consumes: `_dagster_partition_date` from Task 4.
- Produces: `stg_finalsite__contacts` at one row per `finalsite_enrollment_id`,
  now also carrying a `relationships` column of type
  `array<struct<id string, rel_id string, rel_name string, rel_type string, primary bool, financial bool, portal_access bool>>`,
  which Task 6 unnests.

- [ ] **Step 1: Write the failing unit test**

Append to `unit_tests:` in
`src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contacts.yml`.
Two partitions of the same contact go in; the newer one wins and one row
survives:

```yaml
- name: test_contacts_dedupe_newest_partition_wins
  description: Accumulated partitions hold the same contact more than once. The
    newest `_dagster_partition_date` wins and exactly one row survives per
    contact, so the singleton grain every downstream model assumes still holds.
    Guards the `is_primary` and address-of-record picks in #4616 / #4617 / #4680.
  model: stg_finalsite__contacts
  given:
    - input: source('finalsite', 'contacts')
      format: sql
      rows: |
        select
          'con1' as id,
          'Stale' as first_name,
          cast(null as string) as middle_name,
          'Doe' as last_name,
          'Stale Doe' as full_name,
          cast(null as string) as preferred_name,
          'stale@example.com' as email,
          'F' as gender,
          'Female' as gender_display,
          'Female' as gender_full_text,
          'applicant' as status,
          'new' as enrollment_type,
          cast(null as string) as inquiry_submit_date,
          cast(null as string) as application_submit_date,
          cast(null as string) as contract_submit_date,
          struct('5' as canonical_name, 'Grade 5' as name, 'ES' as school_level)
            as grade,
          struct('6' as canonical_name) as prospect_entry_grade,
          struct(2025 as start_year) as school_year,
          struct(2026 as start_year) as prospect_entry_year,
          struct('Cell' as phone_type, '8623007240' as number) as phone_1,
          struct(cast(null as string) as phone_type, cast(null as string) as number)
            as phone_2,
          struct(cast(null as string) as phone_type, cast(null as string) as number)
            as phone_3,
          array<struct<field_name string, value struct<string_value string>>>[]
            as custom_attributes,
          array<struct<field_name string, value struct<string_value string>>>[]
            as id_attributes,
          array<struct<field_name string, value struct<string_value string>>>[]
            as track_attributes,
          '2015-04-05' as birth_date,
          [
            struct(
              'hh1' as id,
              '1 Old St' as address_1,
              cast(null as string) as address_2,
              'Newark' as city,
              'NJ' as state,
              '07102' as zip,
              'US' as country
            )
          ] as households,
          array<
            struct<
              id string,
              rel_id string,
              rel_name string,
              rel_type string,
              `primary` bool,
              financial bool,
              portal_access bool
            >
          >[] as relationships,
          '2026-08-10' as _dagster_partition_date
        union all
        select
          'con1' as id,
          'Fresh' as first_name,
          cast(null as string) as middle_name,
          'Doe' as last_name,
          'Fresh Doe' as full_name,
          cast(null as string) as preferred_name,
          'fresh@example.com' as email,
          'F' as gender,
          'Female' as gender_display,
          'Female' as gender_full_text,
          'enrolled' as status,
          'returning' as enrollment_type,
          cast(null as string) as inquiry_submit_date,
          cast(null as string) as application_submit_date,
          cast(null as string) as contract_submit_date,
          struct('6' as canonical_name, 'Grade 6' as name, 'MS' as school_level)
            as grade,
          struct('6' as canonical_name) as prospect_entry_grade,
          struct(2026 as start_year) as school_year,
          struct(2026 as start_year) as prospect_entry_year,
          struct('Cell' as phone_type, '8623007240' as number) as phone_1,
          struct(cast(null as string) as phone_type, cast(null as string) as number)
            as phone_2,
          struct(cast(null as string) as phone_type, cast(null as string) as number)
            as phone_3,
          array<struct<field_name string, value struct<string_value string>>>[]
            as custom_attributes,
          array<struct<field_name string, value struct<string_value string>>>[]
            as id_attributes,
          array<struct<field_name string, value struct<string_value string>>>[]
            as track_attributes,
          '2015-04-05' as birth_date,
          [
            struct(
              'hh1' as id,
              '2 New Ave' as address_1,
              cast(null as string) as address_2,
              'Newark' as city,
              'NJ' as state,
              '07103' as zip,
              'US' as country
            )
          ] as households,
          array<
            struct<
              id string,
              rel_id string,
              rel_name string,
              rel_type string,
              `primary` bool,
              financial bool,
              portal_access bool
            >
          >[] as relationships,
          '2026-08-11' as _dagster_partition_date
  expect:
    format: sql
    rows: |
      select
        'con1' as finalsite_enrollment_id,
        'Fresh' as first_name,
        'enrolled' as status,
        'returning' as enrollment_type,
        '2 New Ave' as address_1,
        '07103' as zip
```

- [ ] **Step 2: Add `_dagster_partition_date` to the existing unit test
      fixture**

`test_contacts_phone_normalization` supplies an explicit column list, and the
model is about to reference `_dagster_partition_date` in its `order_by`. Add one
line to that fixture's `rows` block (after `] as households`, line 273):

```sql
,
'2026-08-11' as _dagster_partition_date
```

Without this, the existing test fails to compile once Step 3 lands.

- [ ] **Step 3: Run the unit tests to verify the new one fails**

Run:

```bash
cd /workspaces/teamster \
  && uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts/src/dbt/kippnewark \
       --select stg_finalsite__contacts
```

Expected: `test_contacts_dedupe_newest_partition_wins` FAILS with 2 rows
returned where 1 was expected (the model does not dedupe yet).

- [ ] **Step 4: Add the dedupe and the `relationships` passthrough**

`src/dbt/finalsite/models/api/staging/stg_finalsite__contacts.sql` gains a CTE
wrapper. The existing projection is unchanged except for the added
`relationships` column and the new `from` clause:

```sql
with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    source as (select * from {{ source("finalsite", "contacts") }}),

    -- Pulls accumulate one Hive partition per pull date, and a `since` window
    -- re-delivers a contact on every pull that covers it, so the same `id`
    -- appears in many partitions. Keep the newest. `desc` alone is deliberate:
    -- the macro compiles to array_agg(... limit 1) and BigQuery rejects
    -- explicit null-ordering inside an aggregate. See #4715.
    deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="source",
                partition_by="id",
                order_by="_dagster_partition_date desc",
            )
        }}
    )

select
    id as finalsite_enrollment_id,
    -- ... every existing column expression, unchanged ...

    -- passed through whole so stg_finalsite__contact_relationships can unnest
    -- one deduped copy rather than re-reading the accumulated source. Same
    -- contract-widening move `households` already carries for
    -- int_finalsite__contacts__households.
    relationships,
from deduplicated
```

Change only three things in that file: wrap with the two CTEs, add
`relationships,` to the select list, and change the final line from
`from {{ source("finalsite", "contacts") }}` to `from deduplicated`.

- [ ] **Step 5: Declare `relationships` in the enforced contract**

`api/staging` is `+contract: enforced: true`, so the new column must be
declared. Add to the `columns:` list in
`properties/stg_finalsite__contacts.yml`, after the `households` entry:

```yaml
- name: relationships
  data_type:
    array<struct<id string, rel_id string, rel_name string, rel_type string,
    `primary` bool, financial bool, portal_access bool>>
  description:
    Raw bidirectional relationship links for this contact, passed through whole
    so `stg_finalsite__contact_relationships` unnests a deduped copy instead of
    re-reading the accumulated source. `primary` is a per-record singleton and
    is NULL, not false, when unset.
```

- [ ] **Step 6: Run the unit tests to verify both pass**

Run:

```bash
cd /workspaces/teamster \
  && uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts/src/dbt/kippnewark \
       --select stg_finalsite__contacts
```

Expected: `test_contacts_dedupe_newest_partition_wins` PASSES and
`test_contacts_phone_normalization` still PASSES.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts add \
  src/dbt/finalsite/models/api/staging/stg_finalsite__contacts.sql \
  src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contacts.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts commit -m "feat(finalsite): dedupe accumulated contacts partitions to one row per contact

Refs #4715"
```

---

### Task 6: Read the deduped model in `stg_finalsite__contact_relationships`

**Files:**

- Modify:
  `src/dbt/finalsite/models/api/staging/stg_finalsite__contact_relationships.sql`
- Modify:
  `src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contact_relationships.yml`

**Interfaces:**

- Consumes: `stg_finalsite__contacts.relationships` and
  `stg_finalsite__contacts.household_1_id` from Task 5.
- Produces: `stg_finalsite__contact_relationships` at one row per (contact,
  relationship), unchanged column set.

- [ ] **Step 1: Write the failing unit test**

Add a `unit_tests:` entry to
`properties/stg_finalsite__contact_relationships.yml`. Because this model now
reads `stg_finalsite__contacts`, the fixture mocks that ref rather than the
source — which is exactly what proves the fan-out is gone: one contact with two
relationships yields two rows, not two per partition.

```yaml
unit_tests:
  - name: test_relationships_do_not_fan_out_across_partitions
    description: One deduped contact with two relationships yields exactly two
      rows. Reading the deduped model instead of the accumulated source is what
      prevents the cross join multiplying each relationship by the number of
      partitions the contact appears in. See #4715.
    model: stg_finalsite__contact_relationships
    given:
      - input: ref('stg_finalsite__contacts')
        format: sql
        rows: |
          select
            'con1' as finalsite_enrollment_id,
            'hh1' as household_1_id,
            array<struct<field_name string, value struct<boolean_value bool>>>[]
              as custom_attributes,
            [
              struct(
                'rel1' as id,
                'adult1' as rel_id,
                'Ann Doe' as rel_name,
                'mother' as rel_type,
                true as `primary`,
                true as financial,
                true as portal_access
              ),
              struct(
                'rel2' as id,
                'adult2' as rel_id,
                'Bob Doe' as rel_name,
                'father' as rel_type,
                cast(null as bool) as `primary`,
                false as financial,
                false as portal_access
              )
            ] as relationships
    expect:
      format: sql
      rows: |
        select
          'con1' as finalsite_enrollment_id,
          'rel1' as relationship_id,
          'adult1' as rel_id,
          'mother' as rel_type,
          true as is_primary,
          'hh1' as household_1_id
        union all
        select
          'con1' as finalsite_enrollment_id,
          'rel2' as relationship_id,
          'adult2' as rel_id,
          'father' as rel_type,
          cast(null as bool) as is_primary,
          'hh1' as household_1_id
```

- [ ] **Step 2: Run it to verify it fails**

Run:

```bash
cd /workspaces/teamster \
  && uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts/src/dbt/kippnewark \
       --select stg_finalsite__contact_relationships
```

Expected: FAIL — the model still reads `source('finalsite', 'contacts')`, so the
mocked `ref` is unused and the fixture columns do not resolve.

- [ ] **Step 3: Repoint the model**

Replace
`src/dbt/finalsite/models/api/staging/stg_finalsite__contact_relationships.sql`
in full:

```sql
select
    finalsite_enrollment_id,

    r.id as relationship_id,
    r.rel_id,
    r.rel_name,
    r.rel_type,
    r.primary as is_primary,
    r.financial as is_financial,
    r.portal_access as has_portal_access,

    household_1_id,

    -- record-owner fields carried onto the relationship grain so consumers
    -- gating on them (e.g. the contact_2 pick) need no extra joins. These
    -- describe the OWNING contact (`finalsite_enrollment_id`), never the
    -- related person (`rel_id`).
    (
        select logical_or(ca.value.boolean_value),
        from unnest(custom_attributes) as ca
        where ca.field_name = 'is_parent2'
    ) as is_parent2,
from {{ ref("stg_finalsite__contacts") }}
cross join unnest(relationships) as r
```

Two things changed beyond the `from`: `household_1_id` is now read from
`stg_finalsite__contacts` instead of being re-derived as
`c.households[safe_offset(0)].id`, and the `c.` alias is gone.

- [ ] **Step 4: Run it to verify it passes**

Run:

```bash
cd /workspaces/teamster \
  && uv run dbt test --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts/src/dbt/kippnewark \
       --select stg_finalsite__contact_relationships
```

Expected: PASS, 2 rows.

- [ ] **Step 5: Verify nothing downstream broke**

Run:

```bash
cd /workspaces/teamster \
  && uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts/src/dbt/kippnewark \
       --select stg_finalsite__contacts+ --empty
```

Expected: every downstream model compiles and resolves its columns. `--empty`
proves column resolution only, not values — the value proof is cutover step 6.

- [ ] **Step 6: Lint the changed SQL and YAML**

`sqlfluff` and `yamllint` fire at pre-push and in CI, not in the pre-commit
`fmt` hook, so check them explicitly. This takes over two minutes — run it in
the background and read the output only after it exits.

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts \
  && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
       src/dbt/finalsite/models/api/staging/stg_finalsite__contacts.sql \
       src/dbt/finalsite/models/api/staging/stg_finalsite__contact_relationships.sql \
       src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contacts.yml \
       src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contact_relationships.yml \
       src/dbt/finalsite/models/sources-external.yml </dev/null
```

Expected: `No issues`, or only `unformatted file` findings, which the commit
hook fixes. Fix any `file:line` + rule finding before committing.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts add \
  src/dbt/finalsite/models/api/staging/stg_finalsite__contact_relationships.sql \
  src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contact_relationships.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts commit -m "feat(finalsite): unnest relationships from the deduped contacts model

Refs #4715"
```

---

### Task 7: Cutover runbook and spec correction

**Files:**

- Create:
  `docs/superpowers/plans/2026-08-10-finalsite-incremental-contacts-cutover.md`
- Modify:
  `docs/superpowers/specs/2026-08-10-finalsite-incremental-contacts-design.md`

**Interfaces:**

- Consumes: everything above.
- Produces: the ordered manual runbook the cutover follows.

- [ ] **Step 1: Correct the spec's `since_includes_expanded` row**

The Decisions table says `Dropped. Measured no-op.` but the parameter was never
sent — all four code locations passed only `includes`. Change that cell to:

```markdown
| `since_includes_expanded` | Not adopted. Measured no-op, and it was never sent
today. |
```

- [ ] **Step 2: Write the cutover runbook**

Create the file with this content:

````markdown
# Finalsite incremental contacts: cutover runbook

Refs #4715. Run these in order. Steps marked **manual** need a human — they
touch production GCS or the Dagster+ UI.

The external glob `contacts/*` matches recursively, so while both the legacy
root object and partition files exist the table unions them and every `id`
appears twice. That window is steps 3 to 5.

## 1. Record the pre-cutover baseline (manual)

```sql
select count(*) as contacts, count(distinct id) as ids
from `teamster-332318.kippnewark_finalsite.contacts`
```

Repeat for `kippcamden`, `kippmiami`, `kipppaterson`. Expected around 25,052
(kippnewark) and 7,688 (kippmiami). Keep these numbers for step 6.

## 2. Pause the schedules (manual, Dagster+ UI)

Stop all four `<location>__finalsite__contacts__daily_asset_job_schedule`
schedules. Do not rename them.

## 3. Merge the PR and let the deploy land

Confirm every `dagster-cloud-deploy / deploy` check-run reaches a terminal
conclusion — a shared-library change redeploys every consuming location, so
expect one same-named check per location.

## 4. Seed one full partition per district (manual, Dagster+ UI)

For each location, materialize `<location>/finalsite/contacts` for partition
`2026-08-11` with run config:

```yaml
ops:
  <location>__finalsite__contacts:
    config:
      full_pull: true
```

Override the run's `dagster/max_runtime` tag to `3600` for these four runs only
— a full pull is ~20 minutes for kippnewark, well past the new 900s default.
They serialize through the `finalsite_api` pool, so budget ~35 minutes total.

Verify each run's `record_count` metadata matches step 1's baseline, and that
its `since` metadata reads `FULL PULL`.

## 5. Delete the legacy root object (manual, destructive)

One per bucket. Check before deleting:

```bash
gsutil ls -l gs://teamster-kippnewark/dagster/kippnewark/finalsite/contacts/data
gsutil rm gs://teamster-kippnewark/dagster/kippnewark/finalsite/contacts/data
```

Repeat for `teamster-kippcamden`, `teamster-kippmiami`, `teamster-kipppaterson`.

Confirm only partition directories remain:

```bash
gsutil ls gs://teamster-kippnewark/dagster/kippnewark/finalsite/contacts/
```

Expected: only `_dagster_partition_fiscal_year=.../` entries, no bare `data`.

## 6. Rebuild and verify values

Re-stage the external source and rebuild:

```bash
uv run dbt run-operation stage_external_sources \
  --project-dir src/dbt/kippnewark --args "select: finalsite.contacts"
uv run dbt build --project-dir src/dbt/kippnewark --select stg_finalsite__contacts+
```

Then confirm the grain and the count, with `--nouse_cache` so the results cache
cannot mask a stale read:

```sql
select count(*) as rows, count(distinct finalsite_enrollment_id) as ids
from `teamster-332318.kippnewark_finalsite.stg_finalsite__contacts`
```

`rows` must equal `ids`, and both must match step 1's baseline within a day of
churn. The `unique` test on `finalsite_enrollment_id` is the automated form of
this check.

Between steps 4 and 5 expect that `unique` test to FAIL: the seed bumps the
source's data version, the automation sensor rebuilds staging while duplicates
exist. That ordering is deliberate — deleting the root object first would leave
the table empty and ship empty files to DeansList, ParentSquare and Focus. A
loud failed test beats a silent empty shipment.

## 7. Resume the schedules (manual, Dagster+ UI)

Start all four schedules. The next tick is 00:15 or 12:00 ET.

## 8. Confirm the first incremental tick

After the first 00:15 run, check its metadata: `since` should read the previous
day's date, and `record_count` should be in the low thousands, not the tens of
thousands. Then confirm the 01:00 Google Directory sync and 01:25 DeansList ship
read same-day contacts.
````

- [ ] **Step 3: Lint both documents**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts \
  && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
       docs/superpowers/plans/2026-08-10-finalsite-incremental-contacts-cutover.md \
       docs/superpowers/specs/2026-08-10-finalsite-incremental-contacts-design.md </dev/null
```

Expected: `No issues`, or only `unformatted file`, which the commit hook fixes.
The nested fences in the runbook are why its outer block is four backticks.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts add \
  docs/superpowers/plans/2026-08-10-finalsite-incremental-contacts-cutover.md \
  docs/superpowers/specs/2026-08-10-finalsite-incremental-contacts-design.md
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-finalsite-incremental-contacts commit -m "docs(finalsite): add the incremental contacts cutover runbook

Refs #4715"
```

---

## Out of scope

- `status_report` — SFTP, already school-year partitioned.
- The `finalsite_api` pool limit and the shared-IP 403 (#4408).
- Bounded retry in `_request` (#4494).
- Un-pausing kippnewark's ParentSquare extract schedule.
- Any full-refresh mechanism. Hard deletes leak by design; see the spec's Known
  limitations.
- Renaming `stg_finalsite__contact_relationships` to `int_`. Precedent
  (`int_finalsite__contacts__households`) says a model reading a
  contract-widened staging column belongs in `intermediate`, but renaming would
  ripple into `kipptaf`'s `source()` references for no functional gain.
