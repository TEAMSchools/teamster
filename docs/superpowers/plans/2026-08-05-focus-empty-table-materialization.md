# Focus Empty-Table Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A configured Focus table with zero rows in the source is created in
BigQuery as an empty, correctly typed table, so its dbt staging model can be
written before any data arrives.

**Architecture:** Replace the `sql_database` source in the Focus factory with a
thin resource that drives dlt's exported `table_rows` generator directly, so it
can yield `dlt.mark.materialize_table_schema()` when the table produced no data.
Because that marker travels dlt's object path — which always injects `_dlt_id`
and `_dlt_load_id` as REQUIRED — the arrow data path must inject them too, via
dlt's `parquet_normalizer` knobs. Existing populated tables cannot gain REQUIRED
columns in place, so the op also accepts a `refresh` run-config field used once,
post-merge, to drop and recreate them.

**Tech Stack:** Python 3.13, dlt 1.29.1, `dagster-dlt`, SQLAlchemy 2, PyArrow,
BigQuery, pytest, uv.

Spec:
`docs/superpowers/specs/2026-08-05-focus-empty-table-materialization-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize`.
  Branch `cbini/feat/claude-focus-empty-table-materialize`. Use
  `git -C <worktree>` for every git call and run Python from inside the
  worktree.
- Scope is the pipeline change plus the migration mechanism. **No dbt changes in
  this PR** — the 11 staging models are a separate follow-up.
- Illuminate and PowerSchool must not be touched.
- The dlt source name stays `"focus"`. It determines the dlt schema name, which
  the destination's stored schema, pipeline state, and `seen-data` markers are
  keyed on; renaming it would orphan them.
- `build_focus_dlt_assets(...)` keeps its current signature — the code location
  `src/teamster/code_locations/kippmiami/dlt/focus/assets.py` calls it with
  `sql_database_credentials`, `code_location`, `table_name`, `op_tags` and must
  not need edits.
- Keep `reflection_level="full_with_precision"`,
  `table_adapter_callback=remove_nullability_adapter`, and
  `type_adapter_callback=interval_to_microseconds_adapter`. Dropping any of them
  regresses #4676 (Postgres `interval`) or the REQUIRED-mode breakage that
  `remove_nullability_adapter` exists to prevent.
- Keep `loader_file_format="parquet"` on `dlt.run()` (#4733).
- **Never write `dlt.config[...]` inside the op body.** The op's resource
  parameter is named `dlt`, which shadows the module, and `DagsterDltResource`
  has no `.config` attribute — the line raises `AttributeError`. Import the
  accessor directly instead: `from dlt import config as dlt_config` (verified to
  be the same object as `dlt.config`).
- `table_rows` has no defaults except `table_loader_class`; pass every argument
  explicitly, per `libraries/dlt/CLAUDE.md`.
- Python: always `uv run`. Never bare `python`.
- Run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd set to the worktree before pushing.

---

## File Structure

| File                                                              | Responsibility                                                                     |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `src/teamster/libraries/dlt/focus/assets.py` (modify)             | Focus factory: resource wrapper, source, translator, op config, knobs              |
| `tests/libraries/test_dlt_focus_materialize_empty.py` (create)    | Empty-vs-populated resource behavior; emitted-file shape via sqlite                |
| `tests/libraries/test_dlt_focus_type_adapter.py` (modify)         | Existing wiring test asserts `explicit_args`, which the new resource does not have |
| `tests/libraries/test_dlt_replace_loader_file_format.py` (modify) | Its `_run_kwargs` helper calls the op body, whose signature gains `config`         |
| `src/teamster/libraries/dlt/focus/CLAUDE.md` (modify)             | Document the new empty-table behavior and the row-id columns                       |
| `src/teamster/libraries/dlt/CLAUDE.md` (modify)                   | Cross-reference from the shared `replace` section                                  |

The factory stays one file: it is ~110 lines today and the change adds ~50. The
adapters, translator, and factory all change together for one reason.

---

### Task 1: Resource wrapper that materializes the schema of an empty table

**Files:**

- Modify: `src/teamster/libraries/dlt/focus/assets.py`
- Create: `tests/libraries/test_dlt_focus_materialize_empty.py`
- Modify: `tests/libraries/test_dlt_focus_type_adapter.py:88-113`
  (`test_factory_wires_both_adapters_into_the_dlt_source`)

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces:
  - `_build_focus_resource(sql_database_credentials: ConnectionStringCredentials, table_name: str, db_schema: str | None) -> Callable[[], Iterator]`
    — returns the `@dlt.resource`-decorated generator function, named
    `table_name`.
  - `build_focus_source(sql_database_credentials: ConnectionStringCredentials, table_name: str, db_schema: str | None = FOCUS_DB_SCHEMA) -> DltSource`
    — the `@dlt.source(name="focus")` wrapper. `db_schema` exists so tests can
    pass `None` for sqlite, which has no `public` schema.
  - Module constants `FOCUS_SOURCE_NAME = "focus"`,
    `FOCUS_DB_SCHEMA = "public"`, `FOCUS_CHUNK_SIZE = 50000`.
  - `FocusDagsterDltTranslator` keys assets off `data.resource.name`.

- [ ] **Step 1: Write the failing test for the empty and populated cases**

Create `tests/libraries/test_dlt_focus_materialize_empty.py`:

```python
"""The Focus resource materializes a never-loaded table's schema (#4740).

A configured Focus table with no rows produced nothing at all before, so dlt
dropped the load package and BigQuery never got a table. The resource now yields
`materialize_table_schema()` in that case, which creates the table from the
reflected schema.

sqlite stands in for Focus Postgres: the item shapes `table_rows` yields and the
files dlt normalizes from them are backend-generic, and the Codespace cannot
reach Focus (IP allowlist).
"""

import pathlib
import tempfile
from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy as sa
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.extract.extractors import MaterializedEmptyList
from dlt.extract.items import DataItemWithMeta

from teamster.libraries.dlt.focus.assets import _build_focus_resource


@pytest.fixture(name="sqlite_url")
def fixture_sqlite_url() -> Iterator[str]:
    """A sqlite file with a `referrals` table whose row count the test sets."""
    with tempfile.TemporaryDirectory() as tmp:
        yield f"sqlite:///{pathlib.Path(tmp) / 'focus.db'}"


def _seed(url: str, rows: int) -> None:
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "create table referrals ("
                "referral_id integer not null, comment text)"
            )
        )
        for i in range(rows):
            conn.execute(
                sa.text("insert into referrals values (:i, 'c')"), {"i": i}
            )
    engine.dispose()


def _items(url: str) -> list[Any]:
    resource = _build_focus_resource(
        sql_database_credentials=ConnectionStringCredentials(url),
        table_name="referrals",
        db_schema=None,
    )
    return list(resource())


def test_empty_table_yields_materialize_marker(sqlite_url: str) -> None:
    _seed(sqlite_url, rows=0)

    items = _items(sqlite_url)

    assert isinstance(items[-1], MaterializedEmptyList), (
        "a 0-row table must end with materialize_table_schema() so the table"
        " is created"
    )


def test_populated_table_yields_no_materialize_marker(sqlite_url: str) -> None:
    _seed(sqlite_url, rows=3)

    items = _items(sqlite_url)

    assert not any(isinstance(i, MaterializedEmptyList) for i in items)

    data_items = [i for i in items if not isinstance(i, DataItemWithMeta)]
    assert [i.num_rows for i in data_items] == [3]


def test_reflection_hints_precede_the_marker(sqlite_url: str) -> None:
    """The hints marker must come first, or the created table has no columns.

    dlt registers the reflected columns from the `HintsMeta` item; a
    `materialize_table_schema()` that arrived before it would create a table
    holding only the `_dlt_*` columns.
    """
    _seed(sqlite_url, rows=0)

    items = _items(sqlite_url)

    assert isinstance(items[0], DataItemWithMeta)
    assert type(items[0].meta).__name__ == "HintsMeta"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  uv run pytest tests/libraries/test_dlt_focus_materialize_empty.py -v
```

Expected: all three FAIL at import with
`ImportError: cannot import name '_build_focus_resource'`.

- [ ] **Step 3: Replace the `sql_database` source with the wrapper resource**

In `src/teamster/libraries/dlt/focus/assets.py`, add these imports to the
existing block:

```python
import sqlalchemy as sa
from dlt.extract.items import DataItemWithMeta
from dlt.extract.source import DltSource
from dlt.sources.sql_database.helpers import table_rows
```

Remove the now-unused `from dlt.sources.sql_database import sql_database`, but
KEEP `remove_nullability_adapter` from that module.

Add the constants above `FocusDagsterDltTranslator`:

```python
FOCUS_SOURCE_NAME = "focus"
FOCUS_DB_SCHEMA = "public"
FOCUS_CHUNK_SIZE = 50000
```

Add the resource builder and source below `interval_to_microseconds_adapter`:

```python
def _build_focus_resource(
    sql_database_credentials: ConnectionStringCredentials,
    table_name: str,
    db_schema: str | None = FOCUS_DB_SCHEMA,
):
    """Build one full-replace dlt resource for a Focus table.

    Drives the exported ``table_rows`` generator rather than wrapping
    ``sql_table``, so the resource can append
    ``dlt.mark.materialize_table_schema()`` when the source yielded no data. A
    table with 0 rows otherwise produces nothing dlt can act on, normalize drops
    the package, and BigQuery never gets a table — leaving no target for a dbt
    staging model (#4740). Same ``table_rows`` pattern as
    ``libraries/dlt/powerschool/``.

    The engine is created inside the generator, at extract time: the factory runs
    at module import in the code location, which must not open a connection.
    """

    @dlt.resource(name=table_name, write_disposition="replace", parallelized=True)
    def _focus_table() -> Iterator:
        engine = sa.create_engine(
            sql_database_credentials.to_native_representation()
        )
        try:
            saw_data = False

            for item in table_rows(
                engine=engine,
                table=table_name,
                metadata=sa.MetaData(schema=db_schema),
                chunk_size=FOCUS_CHUNK_SIZE,
                backend="pyarrow",
                incremental=None,
                table_adapter_callback=remove_nullability_adapter,
                reflection_level="full_with_precision",
                backend_kwargs={},
                type_adapter_callback=interval_to_microseconds_adapter,
                included_columns=None,
                excluded_columns=None,
                query_adapter_callback=None,
                resolve_foreign_keys=False,
            ):
                # table_rows opens with a HintsMeta item carrying the reflected
                # schema, then yields arrow tables. Only the latter is data.
                if not isinstance(item, DataItemWithMeta):
                    saw_data = True

                yield item

            if not saw_data:
                yield dlt.mark.materialize_table_schema()
        finally:
            engine.dispose()

    return _focus_table


@dlt.source(name=FOCUS_SOURCE_NAME)
def build_focus_source(
    sql_database_credentials: ConnectionStringCredentials,
    table_name: str,
    db_schema: str | None = FOCUS_DB_SCHEMA,
) -> Iterator:
    """One-resource source. The name must stay `focus` — it is the dlt schema
    name the destination's stored schema and state are keyed on."""
    yield _build_focus_resource(
        sql_database_credentials=sql_database_credentials,
        table_name=table_name,
        db_schema=db_schema,
    )
```

In `build_focus_dlt_assets`, replace the
`dlt_source = sql_database.with_args(...)` block with:

```python
    dlt_source: DltSource = build_focus_source(
        sql_database_credentials=sql_database_credentials, table_name=table_name
    )
```

In `FocusDagsterDltTranslator.get_asset_spec`, replace
`data.resource.explicit_args["table"]` with `data.resource.name`. The resource
is named `table_name`, so the asset key is unchanged — but `explicit_args`
exists only on `sql_database`-built resources and would now raise.

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  uv run pytest tests/libraries/test_dlt_focus_materialize_empty.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Update the existing wiring test, which asserts `explicit_args`**

`test_factory_wires_both_adapters_into_the_dlt_source` reads
`dlt_source.resources["gradebook_assignments"].explicit_args`, which the new
resource does not have. Replace that one test function with two that assert the
same wiring behaviorally — the asset key still resolves, and the adapters are
actually invoked during extract:

```python
def test_factory_builds_a_source_with_the_table_named_resource():
    """Guard the wiring the translator depends on.

    The asset key comes from `data.resource.name`, so a resource named anything
    else silently changes every Focus asset key.
    """
    assets = build_focus_dlt_assets(
        sql_database_credentials=ConnectionStringCredentials(
            "postgresql+psycopg://localhost:5432/focus"
        ),
        code_location="kippmiami",
        table_name="gradebook_assignments",
    )

    dlt_source = next(iter(assets.specs)).metadata[META_KEY_SOURCE]

    assert list(dlt_source.resources) == ["gradebook_assignments"]
    assert dlt_source.name == "focus"
    assert next(iter(assets.specs)).key.path == [
        "kippmiami",
        "dlt",
        "focus",
        "gradebook_assignments",
    ]


def test_extract_invokes_both_adapters(monkeypatch, tmp_path):
    """The adapters must reach `table_rows`, not merely exist.

    Uses sqlite (the Codespace cannot reach Focus) and records each adapter call,
    so a factory that stops passing one fails here.
    """
    import sqlalchemy as sa

    from teamster.libraries.dlt.focus import assets as focus_assets

    url = f"sqlite:///{tmp_path / 'focus.db'}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text("create table t (id integer not null, note text)"))
    engine.dispose()

    type_calls: list[object] = []
    table_calls: list[object] = []

    original_type_adapter = focus_assets.interval_to_microseconds_adapter
    original_table_adapter = focus_assets.remove_nullability_adapter

    def spy_type_adapter(col_type):
        type_calls.append(col_type)
        return original_type_adapter(col_type)

    def spy_table_adapter(table):
        table_calls.append(table)
        return original_table_adapter(table)

    monkeypatch.setattr(
        focus_assets, "interval_to_microseconds_adapter", spy_type_adapter
    )
    monkeypatch.setattr(
        focus_assets, "remove_nullability_adapter", spy_table_adapter
    )

    resource = focus_assets._build_focus_resource(
        sql_database_credentials=ConnectionStringCredentials(url),
        table_name="t",
        db_schema=None,
    )
    list(resource())

    assert type_calls, "type_adapter_callback was not passed to table_rows"
    assert table_calls, "table_adapter_callback was not passed to table_rows"
```

Keep every other test in that file unchanged — the direct adapter unit tests and
the `interval` regression tests still apply.

- [ ] **Step 6: Run the whole focus test file**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  uv run pytest tests/libraries/test_dlt_focus_type_adapter.py \
    tests/libraries/test_dlt_focus_materialize_empty.py -v
```

Expected: all pass. If `test_extract_invokes_both_adapters` fails with the
adapters never called, the factory is still passing the module-level function
objects captured at import — read them through the module inside
`_build_focus_resource` (the code in Step 3 does, since it references the bare
names at call time).

- [ ] **Step 7: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  git add src/teamster/libraries/dlt/focus/assets.py \
    tests/libraries/test_dlt_focus_materialize_empty.py \
    tests/libraries/test_dlt_focus_type_adapter.py && \
  git commit -m "feat(dagster): materialize the schema of an empty Focus table

Drives dlt's table_rows generator directly so the resource can yield
materialize_table_schema() when a configured Focus table has no rows, which
creates the BigQuery table from the reflected schema. A never-loaded table
previously produced no load package at all, leaving no target for a dbt
staging model.

The asset key now comes from the resource name; explicit_args exists only on
sql_database-built resources.

Refs #4740"
```

---

### Task 2: Row-id columns and the migration's `refresh` run config

**Files:**

- Modify: `src/teamster/libraries/dlt/focus/assets.py`
- Create: `tests/libraries/test_dlt_focus_op_config.py`
- Modify: `tests/libraries/test_dlt_replace_loader_file_format.py` (its
  `_run_kwargs` helper calls the op body, which gains a `config` parameter)

**Interfaces:**

- Consumes: `build_focus_dlt_assets` from Task 1, unchanged signature.
- Produces:
  - `class FocusDltConfig(Config)` with `refresh: str | None = None`.
  - The op body signature
    `(context: AssetExecutionContext, config: FocusDltConfig, dlt: DagsterDltResource)`.
  - `dlt.run()` receives `refresh=<value>` only when `config.refresh` is set.

- [ ] **Step 1: Write the failing tests**

Create `tests/libraries/test_dlt_focus_op_config.py`:

```python
"""Focus op wiring: row-id knobs and the migration's refresh run config (#4740).

The knobs are load-bearing. `materialize_table_schema()` travels dlt's object
path, which injects `_dlt_id` / `_dlt_load_id` as REQUIRED; without the knobs the
arrow data path omits them and BigQuery rejects the first real load into an
empty-created table with `Field _dlt_load_id is missing in new schema`.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from dlt import config as dlt_config
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.libraries.dlt.focus.assets import (
    FocusDltConfig,
    build_focus_dlt_assets,
)

CREDENTIALS = ConnectionStringCredentials("postgresql+psycopg://localhost:5432/db")

ADD_DLT_ID = "normalize.parquet_normalizer.add_dlt_id"
ADD_DLT_LOAD_ID = "normalize.parquet_normalizer.add_dlt_load_id"


class _RecordingDltResource:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    def run(self, **kwargs: Any) -> Iterator[Any]:
        self.kwargs = kwargs
        return iter(())


class _StubLog:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)


class _StubContext:
    """The op logs the refresh mode, so the context needs a `.log`.

    Nothing else on the context is touched before `dlt.run()`.
    """

    def __init__(self) -> None:
        self.log = _StubLog()


@pytest.fixture(name="focus_assets")
def fixture_focus_assets() -> Any:
    return build_focus_dlt_assets(
        sql_database_credentials=CREDENTIALS,
        code_location="kippmiami",
        table_name="discipline_referrals",
    )


@pytest.fixture(autouse=True)
def reset_knobs() -> Iterator[None]:
    """Leave dlt's in-memory config as it was; it is process-global."""
    yield
    dlt_config[ADD_DLT_ID] = False
    dlt_config[ADD_DLT_LOAD_ID] = False


def _run(
    focus_assets: Any, config: FocusDltConfig, context: Any = None
) -> dict[str, Any]:
    dlt_resource = _RecordingDltResource()

    list(
        focus_assets.op.compute_fn.decorated_fn(
            context=context or _StubContext(), config=config, dlt=dlt_resource
        )
    )

    return dlt_resource.kwargs


def test_op_sets_both_row_id_knobs(focus_assets: Any) -> None:
    dlt_config[ADD_DLT_ID] = False
    dlt_config[ADD_DLT_LOAD_ID] = False

    _run(focus_assets, FocusDltConfig())

    assert dlt_config[ADD_DLT_ID] is True
    assert dlt_config[ADD_DLT_LOAD_ID] is True


def test_refresh_is_omitted_by_default(focus_assets: Any) -> None:
    kwargs = _run(focus_assets, FocusDltConfig())

    assert "refresh" not in kwargs
    assert kwargs["write_disposition"] == "replace"
    assert kwargs["loader_file_format"] == "parquet"


def test_refresh_is_forwarded_when_set(focus_assets: Any) -> None:
    kwargs = _run(focus_assets, FocusDltConfig(refresh="drop_resources"))

    assert kwargs["refresh"] == "drop_resources"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  uv run pytest tests/libraries/test_dlt_focus_op_config.py -v
```

Expected: FAIL at import with
`ImportError: cannot import name 'FocusDltConfig'`.

- [ ] **Step 3: Add the config and the knobs**

In `src/teamster/libraries/dlt/focus/assets.py`, extend the dagster import to
include `Config`, and add the accessor import:

```python
from dagster import AssetExecutionContext, AssetKey, AssetSpec, Config
from dlt import config as dlt_config
```

`from dlt import config as dlt_config` is REQUIRED rather than `dlt.config`: the
op's resource parameter is named `dlt`, shadowing the module, and
`DagsterDltResource` has no `.config` attribute, so `dlt.config[...]` inside the
body raises `AttributeError`. (`libraries/dlt/powerschool/assets.py:306` has
this latent bug; do not copy it.)

Add above `FocusDagsterDltTranslator`:

```python
class FocusDltConfig(Config):
    """Run config for the Focus dlt op.

    `refresh` is unset on every scheduled run. It exists for the one-time
    migration that recreates already-populated tables so they gain the
    `_dlt_id` / `_dlt_load_id` columns — BigQuery refuses to add REQUIRED
    columns to an existing table, so they must be dropped and reloaded
    (`drop_resources`, #4740).
    """

    refresh: str | None = None
```

Replace the op body:

```python
    def _assets(
        context: AssetExecutionContext,
        config: FocusDltConfig,
        dlt: DagsterDltResource,
    ) -> Iterator:
        # Both knobs make the arrow data path carry `_dlt_id` / `_dlt_load_id`,
        # which dlt's object path injects as REQUIRED when
        # `materialize_table_schema()` creates an empty table. Without them the
        # first real load into such a table fails with
        # `Field _dlt_load_id is missing in new schema` (#4740). Set here, not at
        # import: each step runs in its own pod, so it cannot leak to another
        # pipeline. NOT `dlt.config` — `dlt` is the resource parameter here.
        dlt_config["normalize.parquet_normalizer.add_dlt_id"] = True
        dlt_config["normalize.parquet_normalizer.add_dlt_load_id"] = True

        # loader_file_format="parquet": BigQuery schema autodetection rejects the
        # empty jsonl file dlt writes to truncate a `replace` table whose source
        # went to 0 rows. See `replace` write-disposition in ../CLAUDE.md (#4733).
        run_kwargs: dict[str, object] = {
            "write_disposition": "replace",
            "loader_file_format": "parquet",
        }

        if config.refresh is not None:
            context.log.info(f"dlt refresh mode: {config.refresh}")
            run_kwargs["refresh"] = config.refresh

        yield from dlt.run(context=context, **run_kwargs)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  uv run pytest tests/libraries/test_dlt_focus_op_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Fix the existing loader-format test for the new op signature**

`tests/libraries/test_dlt_replace_loader_file_format.py::_run_kwargs` calls
`assets.op.compute_fn.decorated_fn(context=None, dlt=dlt_resource)`, which now
misses the required `config` argument. Update that helper only:

```python
def _run_kwargs(assets: Any, config: Any = None) -> dict[str, Any]:
    """Invoke the asset body with a recording resource and return its run kwargs.

    Nothing in the body touches the context or opens a connection before
    `dlt.run()`, so no live database and no Dagster instance are needed.
    """
    dlt_resource = _RecordingDltResource()

    kwargs: dict[str, Any] = {"context": None, "dlt": dlt_resource}

    # the focus op takes run config; the illuminate op does not
    if "config" in assets.op.compute_fn.decorated_fn.__annotations__:
        from teamster.libraries.dlt.focus.assets import FocusDltConfig

        kwargs["config"] = config or FocusDltConfig()

    list(assets.op.compute_fn.decorated_fn(**kwargs))

    return dlt_resource.kwargs
```

- [ ] **Step 6: Run every dlt library test**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  uv run pytest tests/libraries/ -v -k "dlt"
```

Expected: all pass, including the Illuminate assertions in
`test_dlt_replace_loader_file_format.py` (Illuminate is untouched, so its op
body still takes no `config`).

- [ ] **Step 7: Verify the import path of the changed module**

`kippmiami.definitions` cannot be imported in the Codespace (it resolves Focus
credentials eagerly), so check the edited module alone:

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  uv run python -c "
import teamster.libraries.dlt.focus.assets as m
print('imported:', m.__file__)
print('config field:', m.FocusDltConfig().refresh)
print('source name:', m.FOCUS_SOURCE_NAME)
"
```

Expected: prints the worktree path, `None`, and `focus`.

- [ ] **Step 8: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  git add src/teamster/libraries/dlt/focus/assets.py \
    tests/libraries/test_dlt_focus_op_config.py \
    tests/libraries/test_dlt_replace_loader_file_format.py && \
  git commit -m "feat(dagster): add Focus row-id columns and a refresh run config

Enables dlt's parquet_normalizer row-id knobs so the arrow data path carries
_dlt_id and _dlt_load_id, which the object path injects as REQUIRED when it
creates an empty table. Without them the first real load into such a table
fails with 'Field _dlt_load_id is missing in new schema'.

Adds FocusDltConfig.refresh so the one-time migration that recreates
already-populated tables is a run-config launch rather than a temporary code
change. Unset on every scheduled run.

Refs #4740"
```

---

### Task 3: Close the typed-empty-table verification gap

**Files:**

- Create: `tests/libraries/test_dlt_focus_empty_load_package.py`

**Interfaces:**

- Consumes: `build_focus_source` and `_build_focus_resource` from Task 1;
  `FocusDltConfig` from Task 2.
- Produces: nothing later tasks rely on.

The spec records one gap: the BigQuery lifecycle probe ran with a resource that
had no column hints, so its empty table started with only the `_dlt_*` columns.
This task proves the production shape — that an empty table is created **with
its reflected data columns** — without warehouse access, by inspecting the
normalized load package.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/test_dlt_focus_empty_load_package.py`:

```python
"""The empty-table load package carries the reflected columns, not just `_dlt_*`.

If `materialize_table_schema()` reached dlt before the reflection hints, the
created BigQuery table would hold only `_dlt_load_id` and `_dlt_id`, and every
later load would have to ADD the real columns. This asserts the emitted parquet
already has them.

Extract plus normalize only — no BigQuery credentials are used.
"""

import shutil
import tempfile
from pathlib import Path

import dlt
import pyarrow.parquet as pq
import sqlalchemy as sa
from dlt import config as dlt_config
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.destinations import bigquery

from teamster.libraries.dlt.focus.assets import build_focus_source


def test_empty_table_package_carries_reflected_columns(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'focus.db'}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "create table referrals ("
                "referral_id integer not null, comment text, entry_date date)"
            )
        )
    engine.dispose()

    dlt_config["normalize.parquet_normalizer.add_dlt_id"] = True
    dlt_config["normalize.parquet_normalizer.add_dlt_load_id"] = True

    pipelines_dir = tempfile.mkdtemp(prefix="focus-empty-")
    try:
        pipeline = dlt.pipeline(
            pipeline_name="focus_empty_package_test",
            destination=bigquery(autodetect_schema=True),
            dataset_name="test",
            pipelines_dir=pipelines_dir,
        )

        pipeline.extract(
            build_focus_source(
                sql_database_credentials=ConnectionStringCredentials(url),
                table_name="referrals",
                db_schema=None,
            ),
            loader_file_format="parquet",
        )
        pipeline.normalize()

        package = pipeline.list_normalized_load_packages()[-1]
        info = pipeline.get_load_package_info(package)

        jobs = [
            j for j in info.jobs["new_jobs"]
            if j.job_file_info.table_name == "referrals"
        ]

        assert len(jobs) == 1, "the empty table must produce exactly one job"

        path = Path(jobs[0].file_path)
        assert path.suffix == ".parquet"

        names = pq.read_schema(path).names

        assert "referral_id" in names
        assert "comment" in names
        assert "entry_date" in names
        assert "_dlt_load_id" in names
        assert "_dlt_id" in names
    finally:
        shutil.rmtree(pipelines_dir, ignore_errors=True)
        dlt_config["normalize.parquet_normalizer.add_dlt_id"] = False
        dlt_config["normalize.parquet_normalizer.add_dlt_load_id"] = False
```

- [ ] **Step 2: Run it**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  uv run pytest tests/libraries/test_dlt_focus_empty_load_package.py -v
```

Expected: PASS if the yields are correctly ordered. If it fails on a missing
`referral_id`, the marker is reaching dlt before the hints — in
`_build_focus_resource`, make sure `yield item` happens for the `HintsMeta` item
BEFORE `materialize_table_schema()` is yielded, which the Task 1 code does.

- [ ] **Step 3: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  git add tests/libraries/test_dlt_focus_empty_load_package.py && \
  git commit -m "test(dagster): assert the empty Focus package keeps reflected columns

Closes the gap the design flagged: the BigQuery lifecycle probe ran without
column hints, so it never proved an empty-created table is typed. Asserts the
normalized parquet carries the reflected columns alongside the row-id columns.

Refs #4740"
```

---

### Task 4: Document the behavior

**Files:**

- Modify: `src/teamster/libraries/dlt/focus/CLAUDE.md` (the _Empty source
  tables_ section, lines 62-79)
- Modify: `src/teamster/libraries/dlt/CLAUDE.md` (the `replace`
  write-disposition section)

**Interfaces:**

- Consumes: the shipped behavior from Tasks 1 to 3.
- Produces: nothing.

- [ ] **Step 1: Rewrite the Focus _Empty source tables_ section**

Replace the whole section with:

```markdown
## Empty source tables

A configured table with 0 rows in Focus is **created empty** in BigQuery: the
resource in `assets.py` appends `dlt.mark.materialize_table_schema()` when
`table_rows` yielded no data, so the table exists from the reflected schema and
a staging model can be written before any data arrives (#4740).

Consequences to know:

- **Every Focus table carries `_dlt_id` and `_dlt_load_id`.** The materialize
  marker travels dlt's object path, which injects both as REQUIRED, so the arrow
  data path must supply them too — hence the two
  `normalize.parquet_normalizer.add_dlt_*` knobs set in the op body. Turning
  either off breaks the first real load into an empty-created table with
  `Field _dlt_load_id is missing in new schema`.
- **Adding those columns to an existing table is impossible** (BigQuery:
  `Cannot add required fields to an existing schema`), which is why the rollout
  recreated all populated tables once via run config `refresh: drop_resources`.
  Any future table created outside this path needs the same treatment.
- **Column order differs** between a table created empty (`_dlt_*` first) and
  one created by a data load (`_dlt_*` last). Cosmetic — loads match by name and
  every staging model projects explicitly.
- A table absent from `dagster_<district>_dlt_focus` now means a **config or
  load problem**, not an empty source. That is the diagnostic this change buys.
- A table that empties out AFTER loading is truncated, not dropped — see
  `replace` write-disposition in `../CLAUDE.md` (#4733).
```

- [ ] **Step 2: Add the cross-reference in the shared dlt CLAUDE.md**

Append to the `autodetect_schema=True` bullet in the `replace` write-disposition
section:

```markdown
- **Focus additionally materializes never-loaded tables** — its resource yields
  `materialize_table_schema()` when the source has 0 rows, which requires the
  `normalize.parquet_normalizer.add_dlt_*` knobs and made every Focus table gain
  `_dlt_id` / `_dlt_load_id` (see `focus/CLAUDE.md`, #4740). Illuminate does NOT
  do this: its one absent table is absorbed by the
  `illuminate_repository_unpivot` macro's empty fallback.
```

- [ ] **Step 3: Lint both files**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
    src/teamster/libraries/dlt/focus/CLAUDE.md \
    src/teamster/libraries/dlt/CLAUDE.md </dev/null
```

Expected: no issues beyond prettier reformatting, which the pre-commit hook
fixes.

- [ ] **Step 4: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  git add src/teamster/libraries/dlt/focus/CLAUDE.md \
    src/teamster/libraries/dlt/CLAUDE.md && \
  git commit -m "docs(dagster): document Focus empty-table materialization

Refs #4740"
```

---

### Task 5: Lint, push, and open the PR

**Files:** none changed.

- [ ] **Step 1: Lint every changed file**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
    $(git diff --name-only origin/main...HEAD | while read -r f; do [ -f "$f" ] && printf '%s ' "$f"; done) </dev/null
```

Expected: no issues. This takes more than two minutes over this many files — run
it in the background and read the output file after it exits.

- [ ] **Step 2: Run the full library test suite**

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize && \
  uv run pytest tests/libraries/ -v
```

Expected: all pass. `tests/test_dagster_definitions.py` is NOT expected to pass
in a worktree without dbt manifests — do not treat it as a regression.

- [ ] **Step 3: Push**

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-claude-focus-empty-table-materialize push
```

- [ ] **Step 4: Open the PR**

Use `.github/pull_request_template.md`. The body must state:

- What changed and why, linking `Refs #4740` and the spec path.
- That the 11 staging models are a deliberate follow-up, and why (contract types
  need materialized tables).
- The verification table from the spec, plus the offline test list.
- **The migration is a required post-merge step**, not optional: launch the
  Focus asset job once with run config `refresh: drop_resources` at a quiet
  hour, then confirm all 77 tables. Until it runs, populated tables keep loading
  exactly as today, and the 11 empty ones cannot be created — so the PR is inert
  but safe if the migration is delayed.
- In the Dagster self-review section, note that
  `uv run dagster definitions validate` is not runnable in the Codespace for
  `kippmiami` (Focus credentials resolve eagerly at module load) and that the
  branch deployment is the real check.

---

## Post-merge migration runbook

Not part of the PR, but the plan is incomplete without it.

1. Confirm the `kippmiami` code location has LOADED the merge commit
   (`mcp__dagster__get_location_load_history`).
1. **Pick the window deliberately — this is the riskiest step in the plan.**
   Focus dlt runs at 04:00, 12:00, and 14:00 ET, feeding the midday import chain
   documented in `code_locations/kippmiami/CLAUDE.md`. Two hazards while a table
   is dropped or mid-reload:
   - Focus dbt staging models fail outright if they build in that window.
   - Worse, and silent: `rpt_focus__*` import-once is an **anti-join against the
     dlt snapshot of Focus**. A snapshot reading empty makes the 12:45 delivery
     treat already-imported records as new and re-send them, duplicating them in
     Focus once ops runs the import by hand. That delivery is a plain cron —
     nothing gates it on the upstreams, so it fires mid-migration regardless.

   Run the migration **after the 14:00 ET pull finishes and well before 04:00**
   — never inside 11:00-15:00 ET — and confirm every table is repopulated before
   the next 12:45 delivery.

1. Launch the Focus asset job with run config:

   ```yaml
   ops:
     kippmiami__dlt__focus__<table>:
       config:
         refresh: drop_resources
   ```

   One op block per selected asset. Launching the whole job at once keeps drop
   and load adjacent per table.

1. Confirm afterward: all 77 configured tables exist in
   `dagster_kippmiami_dlt_focus`; the 66 previously-populated ones hold row
   counts consistent with the prior day; the 11 new ones exist with 0 rows and
   their reflected columns; every table now has `_dlt_id` and `_dlt_load_id`.
1. Rebuild the existing Focus staging models.
1. Only then start the follow-up PR for the 11 new staging models.
