import contextlib
import importlib
import json

from dagster import SensorResult, SkipReason, build_sensor_context
from dagster_shared import check

from teamster.core.resources import BIGQUERY_RESOURCE

# `bigquery/__init__.py` rebinds the name `sensors` to the sensor LIST, so
# `import ...bigquery.sensors as x` yields that list rather than the module.
# import_module returns the module itself, which is what monkeypatching needs.
SENSORS_MODULE = "teamster.code_locations.kipptaf.google.bigquery.sensors"


class _StubTable:
    """A table with no mtime, so the sensor never emits a materialization."""

    modified = None


class _StubBigQueryClient:
    def __init__(self):
        self.get_table_calls = 0

    def get_table(self, **kwargs):
        self.get_table_calls += 1

        return _StubTable()


class _StubBigQueryResource:
    """Stands in for BigQueryResource so budget logic is testable offline."""

    def __init__(self, client: _StubBigQueryClient):
        self._client = client

    @contextlib.contextmanager
    def get_client(self):
        yield self._client


class _FakeClock:
    """Advances a fixed step per monotonic() call.

    Makes the sensor's deadline arithmetic deterministic: with step=100 and a
    300s budget, the deadline is 400, checks at 200 and 300 pass, and the check
    at 400 breaks the loop.
    """

    def __init__(self, step: float):
        self._now = 0.0
        self._step = step

    def monotonic(self) -> float:
        self._now += self._step

        return self._now


def test_bigquery_table_sensor():
    from teamster.code_locations.kipptaf.google.bigquery.sensors import (
        bigquery_table_modified_sensor,
    )

    context = build_sensor_context()

    sensor_result = bigquery_table_modified_sensor(
        context=context, db_bigquery=BIGQUERY_RESOURCE
    )

    sensor_result = check.inst(obj=sensor_result, ttype=SensorResult)

    assert sensor_result.asset_events is not None

    for asset_event in sensor_result.asset_events:
        context.log.info(msg=asset_event)

    context.log.info(msg=sensor_result.cursor)


def test_bigquery_table_sensor_cursor_offset():
    """Guards the cursor migration: a cursor written before chunking existed must
    still load, the resume offset must round-trip, and the reserved key must not
    be able to collide with a generated asset identifier.
    """
    from teamster.code_locations.kipptaf.google.bigquery.sensors import (
        OFFSET_CURSOR_KEY,
        asset_selection,
        bigquery_table_modified_sensor,
    )

    # a cursor in the pre-chunking shape: asset identifiers only, no offset key
    legacy_identifier = asset_selection[0].key.to_python_identifier()

    context = build_sensor_context(
        cursor=json.dumps({legacy_identifier: 1.0}),
    )

    sensor_result = check.inst(
        obj=bigquery_table_modified_sensor(
            context=context, db_bigquery=BIGQUERY_RESOURCE
        ),
        ttype=SensorResult,
    )

    cursor = json.loads(check.not_none(value=sensor_result.cursor))

    assert OFFSET_CURSOR_KEY in cursor
    assert isinstance(cursor[OFFSET_CURSOR_KEY], int)
    assert 0 <= cursor[OFFSET_CURSOR_KEY] < len(asset_selection)

    assert OFFSET_CURSOR_KEY not in {
        spec.key.to_python_identifier() for spec in asset_selection
    }


def test_bigquery_table_sensor_budget_exhausted_polls_nothing(monkeypatch):
    """With no budget the loop must break before its first call and leave the
    resume index untouched, so the next tick retries the same slice instead of
    silently skipping it.
    """
    sensors = importlib.import_module(SENSORS_MODULE)

    monkeypatch.setattr(sensors, "TICK_TIME_BUDGET_SECONDS", 0)

    client = _StubBigQueryClient()
    start_offset = 5

    context = build_sensor_context(
        cursor=json.dumps({sensors.OFFSET_CURSOR_KEY: start_offset}),
    )

    sensor_result = check.inst(
        obj=sensors.bigquery_table_modified_sensor(
            context=context, db_bigquery=_StubBigQueryResource(client=client)
        ),
        ttype=SensorResult,
    )

    cursor = json.loads(check.not_none(value=sensor_result.cursor))

    assert client.get_table_calls == 0
    assert cursor[sensors.OFFSET_CURSOR_KEY] == start_offset
    assert not sensor_result.asset_events


def test_bigquery_table_sensor_resumes_mid_sweep(monkeypatch):
    """The core fix: the loop stops once the budget is spent and records the index
    it stopped at, rather than running the whole sweep into the tick timeout.
    """
    sensors = importlib.import_module(SENSORS_MODULE)

    monkeypatch.setattr(sensors, "time", _FakeClock(step=100.0))
    monkeypatch.setattr(sensors, "TICK_TIME_BUDGET_SECONDS", 300)

    client = _StubBigQueryClient()
    start_offset = 4

    assert start_offset + 2 < len(sensors.asset_selection)

    context = build_sensor_context(
        cursor=json.dumps({sensors.OFFSET_CURSOR_KEY: start_offset}),
    )

    sensor_result = check.inst(
        obj=sensors.bigquery_table_modified_sensor(
            context=context, db_bigquery=_StubBigQueryResource(client=client)
        ),
        ttype=SensorResult,
    )

    cursor = json.loads(check.not_none(value=sensor_result.cursor))

    # exactly two assets polled, then the budget ran out
    assert client.get_table_calls == 2
    assert cursor[sensors.OFFSET_CURSOR_KEY] == start_offset + 2

    # a partial slice reports itself as partial, not as a finished empty sweep
    skip_reason = check.inst(obj=sensor_result.skip_reason, ttype=SkipReason)

    assert "resuming at index" in check.not_none(value=skip_reason.skip_message)
