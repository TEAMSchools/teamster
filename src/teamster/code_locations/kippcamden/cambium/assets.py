from teamster.code_locations.kippcamden import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippcamden.cambium.schema import NJGPA_SCHEMA, NJSLA_SCHEMA
from teamster.libraries.cambium.assets import (
    build_partitions_def,
    build_remote_file_regex,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

ssh_resource_key = "ssh_couchdrop"
remote_dir_regex_prefix = f"/data-team/{CODE_LOCATION}/cambium"
key_prefix = [CODE_LOCATION, "cambium"]

DISTRICT_CODE = "1799"

partitions_def = build_partitions_def(
    current_fiscal_year=CURRENT_FISCAL_YEAR.fiscal_year
)

# Cambium has not delivered an NJSLA file yet, so the tail of the njsla and
# njsla_science filenames is a guess. Everything before it is copied from the
# NJGPA file that HAS arrived, and only the token after `Record_File` is
# unknown: Cambium replaced Pearson's trailing `_Spring` with `_GPA` there, so
# NJSLA may carry a subject token, or none at all. The group is optional so the
# asset matches either way.
#
# Permissive is safe here only because remote_dir_regex scopes the listing to
# this feed's own folder. The NJGPA file lives under `cambium/njgpa/` and is
# never in scope, and the sensor anchors its match at the start of the path, so
# `cambium/njsla/` cannot match a path under `cambium/njsla_science/`. If
# Cambium does split NJSLA into one file per subject, two files land in one
# folder and build_sftp_file_asset raises "Found multiple files matching" —
# a loud failure that names the real filenames, which is what we want.
UNKNOWN_FILE_SUFFIX = r"(_\w+)?"

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

njsla = build_sftp_file_asset(
    asset_key=[*key_prefix, "njsla"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njsla",
    remote_file_regex=build_remote_file_regex(
        partitions_def=partitions_def,
        district_code=DISTRICT_CODE,
        filename_suffix_regex=UNKNOWN_FILE_SUFFIX,
    ),
    avro_schema=NJSLA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=partitions_def,
)

# Shares NJSLA_SCHEMA with njsla, the way the two Pearson assets share theirs.
# Cambium has sent neither file, so there is no evidence the science layout
# differs, and one stub is one place to correct when the files arrive.
njsla_science = build_sftp_file_asset(
    asset_key=[*key_prefix, "njsla_science"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njsla_science",
    remote_file_regex=build_remote_file_regex(
        partitions_def=partitions_def,
        district_code=DISTRICT_CODE,
        filename_suffix_regex=UNKNOWN_FILE_SUFFIX,
    ),
    avro_schema=NJSLA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=partitions_def,
)

assets = [
    njgpa,
    njsla,
    njsla_science,
]
