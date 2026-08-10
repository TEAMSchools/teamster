"""Focus op wiring: row-id knobs and the migration's refresh run config (#4740).

The knobs are load-bearing. `materialize_table_schema()` travels dlt's object
path, which injects `_dlt_id` / `_dlt_load_id` as REQUIRED; without the knobs the
arrow data path omits them and BigQuery rejects the first real load into an
empty-created table with `Field _dlt_load_id is missing in new schema`.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from dagster import AssetKey
from dlt import config as dlt_config
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.libraries.dlt.focus.assets import (
    FocusDltConfig,
    build_focus_dlt_assets,
)
from teamster.libraries.dlt.probe import ProbeSignatureConfig, ProbeTable

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
    """The op logs its mode and reads the run's asset selection.

    `selected_asset_keys` drives which tables the narrowed source carries, and
    every test here runs in sensor mode (`probe` set) so the op never opens a
    connection to probe.
    """

    def __init__(self) -> None:
        self.log = _StubLog()
        self.selected_asset_keys = {
            AssetKey(["kippmiami", "dlt", "focus", "discipline_referrals"])
        }


@pytest.fixture(name="focus_assets")
def fixture_focus_assets() -> Any:
    return build_focus_dlt_assets(
        sql_database_credentials=CREDENTIALS,
        code_location="kippmiami",
        tables=[ProbeTable(name="discipline_referrals", cursor_column="updated_at")],
    )


@pytest.fixture(autouse=True)
def reset_knobs() -> Iterator[None]:
    """Leave dlt's in-memory config as it was; it is process-global."""
    yield
    dlt_config[ADD_DLT_ID] = False
    dlt_config[ADD_DLT_LOAD_ID] = False


PROBE = {"discipline_referrals": ProbeSignatureConfig(count=1, max_cursor=None)}


def _config(**kwargs: Any) -> FocusDltConfig:
    """Sensor-mode config: `probe` set, so the op does not open a connection."""
    return FocusDltConfig(probe=PROBE, **kwargs)


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

    _run(focus_assets, _config())

    assert dlt_config[ADD_DLT_ID] is True
    assert dlt_config[ADD_DLT_LOAD_ID] is True


def test_refresh_is_omitted_by_default(focus_assets: Any) -> None:
    kwargs = _run(focus_assets, _config())

    assert "refresh" not in kwargs
    assert kwargs["write_disposition"] == "replace"
    assert kwargs["loader_file_format"] == "parquet"


def test_refresh_is_forwarded_when_set(focus_assets: Any) -> None:
    kwargs = _run(focus_assets, _config(refresh="drop_resources"))

    assert kwargs["refresh"] == "drop_resources"


def test_unrecognized_refresh_raises(focus_assets: Any) -> None:
    """A typo must fail loudly, not silently mean `drop_resources`.

    dlt's `prepare_refresh_source` compares only against `drop_sources` and
    `drop_data`, so any other non-None value takes the `drop_resources` branch
    and recreates every table in the run. Dagster cannot validate this at launch
    (its Pythonic config rejects a `Literal`), so the op guards it.
    """
    with pytest.raises(ValueError, match="refresh must be one of"):
        _run(focus_assets, _config(refresh="drop_resource"))
