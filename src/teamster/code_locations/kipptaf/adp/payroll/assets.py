from dagster import (
    AssetKey,
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
)

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.adp.payroll.schema import (
    GENERAL_LEDGER_FILE_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_asset

asset_key = AssetKey([CODE_LOCATION, "adp", "payroll", "general_ledger_file"])

GENERAL_LEDGER_FILE_PARTITIONS_DEF = MultiPartitionsDefinition(
    {
        "group_code": StaticPartitionsDefinition(["2Z3", "3LE", "47S", "9AM"]),
        "date": DynamicPartitionsDefinition(
            name=f"{asset_key.to_python_identifier()}__date"
        ),
    }
)

general_ledger_file = build_sftp_asset(
    asset_key=asset_key.path,
    remote_dir="/teamster-kipptaf/couchdrop/adp/payroll",
    remote_file_regex=r"adp_payroll_(?P<date>\d+)_(?P<group_code>\w+)\.csv",
    ssh_resource_key="ssh_couchdrop",
    avro_schema=GENERAL_LEDGER_FILE_SCHEMA,
    partitions_def=GENERAL_LEDGER_FILE_PARTITIONS_DEF,
)

assets = [
    general_ledger_file,
]
