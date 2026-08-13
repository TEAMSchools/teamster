"""Unit tests for `loader_file_format="parquet"` on the dlt `replace` factories (#4733).

Focus and Illuminate both pair `autodetect_schema=True` with
`write_disposition="replace"`. Once such a table has loaded data, dlt writes an
EMPTY file for it on any later run that yields no items, so the `replace` root
still gets truncated. That file comes from the object extractor, so it defaults
to `jsonl.gz` — and BigQuery schema autodetection cannot infer a schema from an
empty jsonl file, failing the load with
`400 Schema has no fields. Table: {table}_{uuid}_source`.

An empty parquet carries the dlt schema's columns, so autodetect resolves. These
tests guard the kwarg itself: the mechanism lives in dlt, but silently dropping
`loader_file_format` here would re-break the pipeline the next time a source
table goes empty.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from dagster import AssetKey
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.libraries.dlt.focus.assets import build_focus_dlt_assets
from teamster.libraries.dlt.illuminate.assets import build_illuminate_dlt_assets
from teamster.libraries.dlt.probe import ProbeTable

CREDENTIALS = ConnectionStringCredentials("postgresql+psycopg://localhost:5432/db")


class _RecordingDltResource:
    """Stand-in for `DagsterDltResource` that captures the `run()` kwargs."""

    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    def run(self, **kwargs: Any) -> Iterator[Any]:
        self.kwargs = kwargs
        return iter(())


class _StubLog:
    def info(self, message: str) -> None:
        pass


class _StubRun:
    def __init__(self) -> None:
        self.tags: dict[str, str] = {}


class _StubContext:
    def __init__(self, keys: set[Any]) -> None:
        self.log = _StubLog()
        self.run = _StubRun()
        self.selected_asset_keys = keys


FOCUS_KEY = AssetKey(["kippmiami", "dlt", "focus", "discipline_referrals"])


def _run_kwargs(assets: Any, config: Any = None) -> dict[str, Any]:
    """Invoke the asset body with a recording resource and return its run kwargs.

    Nothing in the body touches the context or opens a connection before
    `dlt.run()`, so no live database and no Dagster instance are needed.
    """
    dlt_resource = _RecordingDltResource()

    kwargs: dict[str, Any] = {"context": None, "dlt": dlt_resource}

    # the focus op takes run config and reads the context; the illuminate op does
    # neither
    if "config" in assets.op.compute_fn.decorated_fn.__annotations__:
        from teamster.libraries.dlt.focus.assets import FocusDltConfig
        from teamster.libraries.dlt.probe import ProbeSignatureConfig

        kwargs["context"] = _StubContext({FOCUS_KEY})
        kwargs["config"] = config or FocusDltConfig(
            probe={
                "discipline_referrals": ProbeSignatureConfig(count=1, max_cursor=None)
            }
        )

    # consume the generator so the `yield from dlt.run(...)` line executes
    list(assets.op.compute_fn.decorated_fn(**kwargs))

    return dlt_resource.kwargs


@pytest.fixture(name="focus_assets")
def fixture_focus_assets() -> Any:
    return build_focus_dlt_assets(
        sql_database_credentials=CREDENTIALS,
        code_location="kippmiami",
        tables=[ProbeTable(name="discipline_referrals", cursor_column="updated_at")],
    )


@pytest.fixture(name="illuminate_assets")
def fixture_illuminate_assets() -> Any:
    return build_illuminate_dlt_assets(
        sql_database_credentials=CREDENTIALS,
        code_location="kipptaf",
        schema="dna_assessments",
        table_name="agg_student_responses",
    )


def test_focus_factory_loads_as_parquet(focus_assets: Any) -> None:
    kwargs = _run_kwargs(focus_assets)

    assert kwargs["loader_file_format"] == "parquet"
    assert kwargs["write_disposition"] == "replace"


def test_illuminate_factory_loads_as_parquet(illuminate_assets: Any) -> None:
    kwargs = _run_kwargs(illuminate_assets)

    assert kwargs["loader_file_format"] == "parquet"
    assert kwargs["write_disposition"] == "replace"


def test_dlt_run_accepts_loader_file_format() -> None:
    """`DagsterDltResource.run` forwards `**kwargs` to `Pipeline.run`.

    Without this, passing `loader_file_format` would raise `TypeError` at
    runtime instead of taking effect — the kwarg reaches dlt only because the
    wrapper is signature-agnostic and `Pipeline.run` declares the parameter.
    """
    import inspect

    from dagster_dlt import DagsterDltResource
    from dlt.pipeline.pipeline import Pipeline

    wrapper_params = inspect.signature(DagsterDltResource.run).parameters
    pipeline_params = inspect.signature(Pipeline.run).parameters

    assert any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in wrapper_params.values()
    ), "DagsterDltResource.run no longer accepts **kwargs"

    assert "loader_file_format" in pipeline_params
