"""Unit tests for PowerSchool SIS ODBC schedule factory."""

from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from dagster import AssetKey, AssetsDefinition, RunRequest

from teamster.libraries.powerschool.sis.odbc.utils import StalenessResult


class TestBuildPowerschoolSisAssetSchedule:
    @patch("teamster.libraries.powerschool.sis.odbc.schedules.evaluate_asset_staleness")
    @patch("teamster.libraries.powerschool.sis.odbc.schedules.powerschool_connection")
    def test_groups_run_requests_by_partitions_def_and_key(
        self, mock_conn_ctx, mock_eval
    ):
        from teamster.libraries.powerschool.sis.odbc.schedules import (
            build_powerschool_sis_asset_schedule,
        )

        mock_conn = MagicMock()
        mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

        mock_eval.return_value = [
            StalenessResult(
                asset_key=AssetKey(["loc", "powerschool", "students"]),
                partitions_def_identifier=None,
                partition_key=None,
            ),
            StalenessResult(
                asset_key=AssetKey(["loc", "powerschool", "schools"]),
                partitions_def_identifier=None,
                partition_key=None,
            ),
        ]

        asset1 = MagicMock(spec=AssetsDefinition)
        asset1.key = AssetKey(["loc", "powerschool", "students"])
        asset2 = MagicMock(spec=AssetsDefinition)
        asset2.key = AssetKey(["loc", "powerschool", "schools"])

        schedule_def = build_powerschool_sis_asset_schedule(
            code_location="loc",
            execution_timezone=ZoneInfo("America/New_York"),
            cron_schedule="0 0 * * *",
            asset_selection=[asset1, asset2],
        )

        # Access the underlying decorated function to bypass Dagster invocation
        inner_fn = schedule_def._execution_fn.decorated_fn

        context = MagicMock()
        context.instance = MagicMock()
        ssh = MagicMock()
        db = MagicMock()

        run_requests = list(inner_fn(context, ssh, db))

        assert len(run_requests) == 1
        assert isinstance(run_requests[0], RunRequest)
        assert run_requests[0].run_key == "_"
        assert len(run_requests[0].asset_selection) == 2
