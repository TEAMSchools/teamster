from types import SimpleNamespace

import pytest
from dagster import SkipReason, build_sensor_context

from teamster.code_locations.kipptaf.adp.payroll.sensors import (
    adp_payroll_sftp_sensor,
)
from teamster.code_locations.kipptaf.adp.workforce_now.sftp.sensors import (
    adp_wfn_sftp_sensor,
)
from teamster.code_locations.kipptaf.deanslist.sensors import deanslist_sftp_sensor


@pytest.mark.parametrize(
    ("sftp_sensor", "resource_key"),
    [
        (deanslist_sftp_sensor, "ssh_deanslist"),
        (adp_payroll_sftp_sensor, "ssh_couchdrop"),
        (adp_wfn_sftp_sensor, "ssh_adp_workforce_now"),
    ],
)
def test_transient_listing_failure_skips_tick(sftp_sensor, resource_key):
    """A downed host must skip the tick, not fail it: these sensors go through
    listdir_attr_r_or_skip like every other SFTP sensor."""
    skip = SkipReason("host unreachable")
    ssh = SimpleNamespace(listdir_attr_r_or_skip=lambda **kwargs: skip)

    result = sftp_sensor(
        context=build_sensor_context(sensor_name=sftp_sensor.name),
        **{resource_key: ssh},
    )

    assert result is skip
