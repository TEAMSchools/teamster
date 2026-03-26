"""Unit tests for PowerSchool SIS ODBC sensor factory."""

from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from dagster import AssetKey, AssetsDefinition, SensorResult

from teamster.libraries.powerschool.sis.odbc.utils import StalenessResult


class TestBuildPowerschoolAssetSensor:
    @patch("teamster.libraries.powerschool.sis.odbc.sensors.evaluate_asset_staleness")
    @patch("teamster.libraries.powerschool.sis.odbc.sensors.powerschool_connection")
    def test_returns_sensor_result_with_grouped_run_requests(
        self, mock_conn_ctx, mock_eval
    ):
        from teamster.libraries.powerschool.sis.odbc.sensors import (
            build_powerschool_asset_sensor,
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
        asset1.partitions_def = None
        asset2 = MagicMock(spec=AssetsDefinition)
        asset2.key = AssetKey(["loc", "powerschool", "schools"])
        asset2.partitions_def = None

        sensor_def = build_powerschool_asset_sensor(
            code_location="loc",
            execution_timezone=ZoneInfo("America/New_York"),
            asset_selection=[asset1, asset2],
        )

        # Access the underlying decorated function to bypass Dagster invocation
        inner_fn = sensor_def._raw_fn

        context = MagicMock()
        context.instance = MagicMock()
        ssh = MagicMock()
        db = MagicMock()

        result = inner_fn(context, ssh, db)

        assert isinstance(result, SensorResult)
        assert len(result.run_requests) == 1
        assert len(result.run_requests[0].asset_selection) == 2
        assert (
            "loc__powerschool__sis__asset_job_None" in result.run_requests[0].job_name
        )

    @patch("teamster.libraries.powerschool.sis.odbc.sensors.evaluate_asset_staleness")
    @patch("teamster.libraries.powerschool.sis.odbc.sensors.powerschool_connection")
    def test_empty_results_returns_sensor_result(self, mock_conn_ctx, mock_eval):
        from teamster.libraries.powerschool.sis.odbc.sensors import (
            build_powerschool_asset_sensor,
        )

        mock_conn = MagicMock()
        mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_eval.return_value = []

        asset = MagicMock(spec=AssetsDefinition)
        asset.key = AssetKey(["loc", "powerschool", "students"])
        asset.partitions_def = None

        sensor_def = build_powerschool_asset_sensor(
            code_location="loc",
            execution_timezone=ZoneInfo("America/New_York"),
            asset_selection=[asset],
        )

        inner_fn = sensor_def._raw_fn

        result = inner_fn(MagicMock(), MagicMock(), MagicMock())

        assert isinstance(result, SensorResult)
        assert len(result.run_requests) == 0
