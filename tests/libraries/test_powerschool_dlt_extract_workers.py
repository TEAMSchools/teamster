"""Unit tests for the dlt extract-worker concurrency cap (DPY-4011 fix).

Covers `_resolve_extract_workers`: a per-run `dlt_extract_workers` tag
overrides the factory's `max_extract_workers` param, which overrides dlt's
default (unset EXTRACT__WORKERS -> dlt's default of 5).

Also covers the op body itself: `_resolve_extract_workers` alone doesn't prove
the resolved value ever reaches dlt. The op previously wrote it to `dlt.config`
-- `dlt` is the resource parameter here, shadowing the top-level `dlt` module,
so that assignment raised `AttributeError` the moment anyone set the tag. These
tests run the op body far enough to reach that line and assert the module-level
`dlt.config` (imported here as `dlt_config`, matching the op's import) actually
received the value.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from dagster import AssetKey
from dlt import config as dlt_config
from dlt.common.configuration.exceptions import ConfigFieldMissingException

from teamster.libraries.dlt.powerschool.assets import (
    PowerSchoolDltConfig,
    _resolve_extract_workers,
    build_powerschool_dlt_assets,
)
from teamster.libraries.dlt.probe import ProbeSignatureConfig, ProbeTable

EXTRACT_WORKERS = "extract.workers"


def test_resolve_extract_workers_no_tag_no_param_leaves_default():
    assert _resolve_extract_workers(None, None) is None


def test_resolve_extract_workers_no_tag_uses_param():
    assert _resolve_extract_workers(None, 1) == 1


def test_resolve_extract_workers_tag_overrides_param():
    assert _resolve_extract_workers("3", 1) == 3


def test_resolve_extract_workers_tag_no_param():
    assert _resolve_extract_workers("2", None) == 2


class _FakeRunResult:
    """Stand-in for dlt's `LoadInfo`; the op iterates it for materializations."""

    def __iter__(self) -> Iterator[Any]:
        return iter(())


class _RecordingDltResource:
    """Stand-in for `DagsterDltResource` that records the `run()` kwargs."""

    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    def run(self, **kwargs: Any) -> _FakeRunResult:
        self.kwargs = kwargs
        return _FakeRunResult()


class _StubLog:
    def info(self, message: str) -> None:
        pass


class _StubRun:
    def __init__(self, tags: dict[str, str] | None = None) -> None:
        self.tags = tags or {}


class _StubContext:
    def __init__(self, keys: set[AssetKey], tags: dict[str, str] | None = None) -> None:
        self.log = _StubLog()
        self.run = _StubRun(tags)
        self.selected_asset_keys = keys


class _StubSSH:
    @contextmanager
    def open_ssh_tunnel(self) -> Iterator[None]:
        yield


class _StubOracle:
    def connection_url(self) -> str:
        return "oracle+oracledb://u:p@localhost:1521/?service_name=s"


TABLE = ProbeTable(name="students", cursor_column="transaction_date")
PROBE = {"students": ProbeSignatureConfig(count=1, max_cursor=None)}


@pytest.fixture(autouse=True)
def reset_extract_workers() -> Iterator[None]:
    """Leave dlt's in-memory config as it was; it is process-global."""
    yield
    dlt_config[EXTRACT_WORKERS] = None


def _run_op(tags: dict[str, str] | None = None) -> None:
    assets_def: Any = build_powerschool_dlt_assets(
        code_location="kipppaterson", tables=[TABLE]
    )
    context = _StubContext(
        keys={AssetKey(["kipppaterson", "powerschool", "sis", "students"])},
        tags=tags,
    )

    # config.probe is set (sensor mode), so the op never opens a real DB
    # connection to probe -- the stubbed ssh tunnel and connection_url() are
    # only there to satisfy the op's parameter list.
    list(
        assets_def.op.compute_fn.decorated_fn(
            context=context,
            config=PowerSchoolDltConfig(probe=PROBE),
            dlt=_RecordingDltResource(),
            ssh_powerschool=_StubSSH(),
            db_powerschool=_StubOracle(),
        )
    )


def test_op_sets_extract_workers_from_tag() -> None:
    dlt_config[EXTRACT_WORKERS] = None

    _run_op(tags={"dlt_extract_workers": "3"})

    assert dlt_config[EXTRACT_WORKERS] == 3


def test_op_leaves_extract_workers_unset_without_tag() -> None:
    dlt_config[EXTRACT_WORKERS] = None

    _run_op()

    # dlt_config[...] raises when a field is unset -- that IS "unset" here.
    with pytest.raises(ConfigFieldMissingException):
        dlt_config[EXTRACT_WORKERS]
