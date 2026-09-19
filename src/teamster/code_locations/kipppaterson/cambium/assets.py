from teamster.code_locations.kipppaterson import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kipppaterson.cambium.schema import NJSLA_SCHEMA
from teamster.libraries.cambium.assets import (
    build_partitions_def,
    build_remote_file_regex,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

ssh_resource_key = "ssh_couchdrop"
remote_dir_regex_prefix = f"/data-team/{CODE_LOCATION}/cambium"
key_prefix = [CODE_LOCATION, "cambium"]

DISTRICT_CODE = "7899"

partitions_def = build_partitions_def(
    current_fiscal_year=CURRENT_FISCAL_YEAR.fiscal_year,
    # Spring 2026 is the first administration New Jersey reported through
    # Cambium; everything before it came through Pearson.
    first_administration_year=2026,
    # Spring is the only season Cambium sends. The fall tokens were Pearson-era
    # cruft and never appeared in a Cambium filename.
    administrations=["Spring"],
)

# NJSLA only. Paterson does not sit for NJGPA, so Cambium sends it no NJGPA
# file, and stg_pearson__njgpa is disabled in the kipppaterson dbt project.
njsla = build_sftp_file_asset(
    asset_key=[*key_prefix, "njsla"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njsla",
    remote_file_regex=build_remote_file_regex(
        partitions_def=partitions_def,
        district_code=DISTRICT_CODE,
        filename_suffix_regex=r"_SLA",
    ),
    avro_schema=NJSLA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=partitions_def,
)

assets = [
    njsla,
]
