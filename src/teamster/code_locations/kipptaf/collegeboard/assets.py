from dagster import StaticPartitionsDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.collegeboard.schema import PSAT_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_folder_asset

psat = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "collegeboard", "psat"],
    remote_dir_regex=r"/data-team/kipptaf/collegeboard/psat",
    remote_file_regex=r"\d+_(?P<test_type>\w+)_\d+_\d+\.csv",
    ssh_resource_key="ssh_couchdrop",
    avro_schema=PSAT_SCHEMA,
    partitions_def=StaticPartitionsDefinition(["PSAT10", "PSAT89", "PSATNM"]),
)

assets = [
    psat,
]
