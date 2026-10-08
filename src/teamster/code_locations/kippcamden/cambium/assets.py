from teamster.code_locations.kippcamden import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippcamden.cambium.schema import NJGPA_SCHEMA, NJSLA_SCHEMA
from teamster.libraries.cambium.assets import (
    build_partitions_def,
    build_remote_file_regex,
)
from teamster.libraries.sftp.assets import (
    build_sftp_file_asset,
    build_sftp_folder_asset,
)

ssh_resource_key = "ssh_couchdrop"
remote_dir_regex_prefix = f"/data-team/{CODE_LOCATION}/cambium"
key_prefix = [CODE_LOCATION, "cambium"]

DISTRICT_CODE = "1799"

partitions_def = build_partitions_def(
    current_fiscal_year=CURRENT_FISCAL_YEAR.fiscal_year,
    # Spring 2026 is the first administration New Jersey reported through
    # Cambium; everything before it came through Pearson.
    first_administration_year=2026,
    # Spring is the only season Cambium sends. The fall tokens were Pearson-era
    # cruft and never appeared in a Cambium filename.
    administrations=["Spring"],
)

njgpa = build_sftp_file_asset(
    asset_key=[*key_prefix, "njgpa"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njgpa",
    remote_file_regex=build_remote_file_regex(
        partitions_def=partitions_def,
        district_code=DISTRICT_CODE,
        filename_suffix_regex=r"_GPA",
    ),
    avro_schema=NJGPA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=partitions_def,
)

# One asset over the NJSLA file and the end-of-course (EOC) file, which share a
# header. A re-issued NJSLA file can bundle the EOC tests too, so both files
# land in one relation and stg_cambium__njsla keeps the newest copy of each
# test. Both files land in the same Couchdrop folder.
njsla = build_sftp_folder_asset(
    asset_key=[*key_prefix, "njsla"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njsla",
    remote_file_regex=build_remote_file_regex(
        partitions_def=partitions_def,
        district_code=DISTRICT_CODE,
        filename_suffix_regex=r"_SLA(?:_EOC)?",
    ),
    avro_schema=NJSLA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=partitions_def,
    add_source_file_modified_timestamp=True,
)

assets = [
    njgpa,
    njsla,
]
