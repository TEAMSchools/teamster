"""The op's full-refresh branch (`config.probe is None`) probes before it loads.

Every other op test in this package runs in sensor mode (`probe` set) so the op
never opens a connection -- see `test_dlt_focus_op_config.py`. This exercises
the other branch: no run config means the op probes the selection itself, over
a real sqlite database standing in for Focus Postgres, and must pass
`build_focus_source` the SAME signatures `probe_signature` computes directly
against that database.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import sqlalchemy as sa
from dagster import AssetKey
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.libraries.dlt.focus import assets as focus_assets_module
from teamster.libraries.dlt.focus.assets import FocusDltConfig, build_focus_dlt_assets
from teamster.libraries.dlt.probe import ProbeTable, probe_signature


class _RecordingDltResource:
    """Stand-in for `DagsterDltResource` that records the `run()` call and
    when it happened, relative to the probe, in the shared `events` list."""

    def __init__(self, events: list[str]) -> None:
        self.kwargs: dict[str, Any] = {}
        self._events = events

    def run(self, **kwargs: Any) -> Iterator[Any]:
        self._events.append("load")
        self.kwargs = kwargs
        return iter(())


class _StubLog:
    def info(self, message: str) -> None:
        pass


class _StubRun:
    def __init__(self) -> None:
        self.tags: dict[str, str] = {}


class _StubContext:
    def __init__(self, keys: set[AssetKey]) -> None:
        self.log = _StubLog()
        self.run = _StubRun()
        self.selected_asset_keys = keys


def _seed_sqlite(url: str) -> None:
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            sa.text("create table referrals (referral_id integer not null, note text)")
        )
        conn.execute(sa.text("insert into referrals values (1, 'a')"))
        conn.execute(sa.text("insert into referrals values (2, 'b')"))
    engine.dispose()


def test_full_refresh_probes_before_load_with_matching_signatures(
    tmp_path: Path,
) -> None:
    url = f"sqlite:///{tmp_path / 'focus.db'}"
    _seed_sqlite(url)

    credentials = ConnectionStringCredentials(url)
    table = ProbeTable(name="referrals", cursor_column=None)

    focus_assets: Any = build_focus_dlt_assets(
        sql_database_credentials=credentials,
        code_location="kippmiami",
        tables=[table],
    )

    events: list[str] = []
    dlt_resource = _RecordingDltResource(events)
    context = _StubContext({AssetKey(["kippmiami", "dlt", "focus", "referrals"])})

    real_probe_signature = focus_assets_module.probe_signature

    def _spy_probe_signature(connection, table_name, cursor_column):
        events.append("probe")
        return real_probe_signature(connection, table_name, cursor_column)

    with (
        patch.object(
            focus_assets_module, "probe_signature", side_effect=_spy_probe_signature
        ),
        patch.object(
            focus_assets_module,
            "build_focus_source",
            wraps=focus_assets_module.build_focus_source,
        ) as source_spy,
    ):
        list(
            focus_assets.op.compute_fn.decorated_fn(
                context=context, config=FocusDltConfig(probe=None), dlt=dlt_resource
            )
        )

    assert events == ["probe", "load"], "the op must probe before it loads"

    expected_engine = sa.create_engine(url)
    try:
        with expected_engine.connect() as connection:
            expected_signature = probe_signature(connection, "referrals", None)
    finally:
        expected_engine.dispose()

    assert source_spy.call_args.kwargs["signatures"] == {
        "referrals": expected_signature
    }
