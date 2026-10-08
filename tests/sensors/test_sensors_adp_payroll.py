import re
from contextlib import nullcontext
from types import SimpleNamespace

from dagster import MultiPartitionKey, SensorResult, build_sensor_context
from dagster_shared import check

from teamster.code_locations.kipptaf.adp.payroll.assets import (
    GENERAL_LEDGER_FILE_PARTITIONS_DEF,
    general_ledger_file,
)
from teamster.code_locations.kipptaf.adp.payroll.sensors import (
    adp_payroll_sftp_sensor,
)
from teamster.libraries.sftp.assets import compose_regex

REMOTE_DIR = "/teamster-kipptaf/couchdrop/adp/payroll"
FILENAME = "ADP_Payroll_20260815_47s.csv"


def test_sensor_uppercases_group_code():
    sftp_client = SimpleNamespace()
    ssh_couchdrop = SimpleNamespace(
        get_connection=lambda: nullcontext(
            SimpleNamespace(open_sftp=lambda: nullcontext(sftp_client))
        ),
        listdir_attr_r=lambda **kwargs: [
            (
                SimpleNamespace(filename=FILENAME, st_mtime=100.0, st_size=1),
                f"{REMOTE_DIR}/{FILENAME}",
            )
        ],
    )

    result = check.inst(
        adp_payroll_sftp_sensor(
            context=build_sensor_context(), ssh_couchdrop=ssh_couchdrop
        ),
        SensorResult,
    )

    [run_request] = check.not_none(result.run_requests)
    partition_key = check.inst(run_request.partition_key, MultiPartitionKey)

    assert partition_key.keys_by_dimension["group_code"] == "47S"
    assert (
        "47S"
        in GENERAL_LEDGER_FILE_PARTITIONS_DEF.get_partitions_def_for_dimension(
            "group_code"
        ).get_partition_keys()
    )


def test_asset_regex_matches_lowercase_group_code():
    remote_file_regex = general_ledger_file.metadata_by_key[general_ledger_file.key][
        "remote_file_regex"
    ]

    composed = compose_regex(
        regexp=remote_file_regex,
        partition_key=MultiPartitionKey({"date": "20260815", "group_code": "47S"}),
    )

    assert re.search(
        pattern=f"{REMOTE_DIR}/{composed}", string=f"{REMOTE_DIR}/{FILENAME}"
    )
