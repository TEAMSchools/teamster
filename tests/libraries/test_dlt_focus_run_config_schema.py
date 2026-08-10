"""Regression guard: the op name and FOCUS_SOURCE_NAME must match run config.

Mirrors `test_dlt_powerschool_assets.py`'s `_resolved_probe_job` test. Both the
sensor's probe payload and the 04:00 schedule's empty run config (full refresh)
must validate against the REAL asset job built by `build_focus_dlt_assets` --
this is what catches a future rename of the op name or `FOCUS_SOURCE_NAME`
before it fails only at run launch in production.
"""

from dagster import Definitions, define_asset_job, validate_run_config
from dagster_dlt import DagsterDltResource
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.libraries.dlt.focus.assets import build_focus_dlt_assets
from teamster.libraries.dlt.probe import ProbeTable

CREDENTIALS = ConnectionStringCredentials("postgresql+psycopg://localhost:5432/db")


def _resolved_probe_job():
    tables = [
        ProbeTable(name="students", cursor_column="updated_at"),
        ProbeTable(name="co_teachers", cursor_column=None),
    ]

    assets_def = build_focus_dlt_assets(
        sql_database_credentials=CREDENTIALS,
        code_location="kippmiami",
        tables=tables,
    )

    defs = Definitions(
        assets=[assets_def],
        jobs=[define_asset_job("probe_job", selection=list(assets_def.keys))],
        resources={"dlt": DagsterDltResource()},
    )
    return defs.resolve_job_def("probe_job")


def test_run_config_schema_accepts_probe_payload():
    job = _resolved_probe_job()

    validated = validate_run_config(
        job,
        {
            "ops": {
                "kippmiami__dlt__focus": {
                    "config": {
                        "probe": {
                            "students": {
                                "count": 43,
                                "max_cursor": "2026-08-09T00:00:00",
                            },
                            "co_teachers": {"count": 5, "max_cursor": None},
                        }
                    }
                }
            }
        },
    )

    assert validated


def test_run_config_schema_accepts_empty_full_refresh():
    job = _resolved_probe_job()

    assert validate_run_config(job, {})
