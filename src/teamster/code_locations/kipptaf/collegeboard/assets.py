from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kipptaf.collegeboard.schema import AP_SCHEMA, PSAT_SCHEMA
from teamster.libraries.sftp.assets import (
    build_sftp_file_asset,
    build_sftp_folder_asset,
)

psat = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "collegeboard", "psat"],
    remote_dir_regex=r"/data-team/kipptaf/collegeboard/psat",
    remote_file_regex=r"\d+_(?P<test_type>\w+)_\d+_\d+\.csv",
    ssh_resource_key="ssh_couchdrop",
    avro_schema=PSAT_SCHEMA,
    partitions_def=StaticPartitionsDefinition(["PSAT10", "PSAT89", "PSATNM"]),
)

ap = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "collegeboard", "ap"],
    remote_dir_regex=(
        r"/data-team/kipptaf/collegeboard/ap/(?P<school_year>\d+)/(?P<school>[A-Za-z])"
    ),
    remote_file_regex=r".+\.csv",
    file_dtype=str,
    ssh_resource_key="ssh_couchdrop",
    avro_schema=AP_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "school": StaticPartitionsDefinition(["KHS", "Lab", "NCA"]),
            "school_year": StaticPartitionsDefinition(
                [str(y) for y in range(2018, CURRENT_FISCAL_YEAR.fiscal_year)]
            ),
        }
    ),
)

assets = [
    ap,
    psat,
]
