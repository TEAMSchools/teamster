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
