import importlib
import json

import pytest
from dagster import SensorResult, build_sensor_context

from teamster.core.resources import SSH_IREADY


def _test_sensor(sftp_sensor, cursor=None, **kwargs):
    if cursor is None:
        cursor = {}

    context = build_sensor_context(
        sensor_name=sftp_sensor.name, cursor=json.dumps(obj=cursor)
    )

    result: SensorResult = sftp_sensor(context=context, **kwargs)

    assert result.run_requests is not None
    assert len(result.run_requests) > 0

    for run_request in result.run_requests:
        context.log.info(run_request)


@pytest.mark.parametrize("code_location", ["kippmiami", "kippnewark"])
def test_iready_sftp_sensor_jobs_run_in_run_pod(code_location):
    sftp_sensor = importlib.import_module(
        f"teamster.code_locations.{code_location}.iready.sensors"
    ).sftp_sensor

    assert sftp_sensor.targets
    for target in sftp_sensor.targets:
        job = target.resolvable_to_job
        assert job.executor_def.name == "in_process", job.name


def test_iready_sftp_sensor_kippmiami():
    from teamster.code_locations.kippmiami.iready.sensors import sftp_sensor

    _test_sensor(sftp_sensor=sftp_sensor, ssh_iready=SSH_IREADY)


def test_iready_sftp_sensor_kippnewark():
    from teamster.code_locations.kippnewark.iready.sensors import sftp_sensor

    _test_sensor(
        sftp_sensor=sftp_sensor,
        ssh_iready=SSH_IREADY,
        cursor={
            "kippnewark__iready__diagnostic_results": 1761033257.001213,
            "kippnewark__iready__instructional_usage_data": 1753089158.216589,
            "kippnewark__iready__personalized_instruction_by_lesson": 1761033257.001213,
            "kippnewark__iready__instruction_by_lesson": 1761033257.001213,
        },
    )
