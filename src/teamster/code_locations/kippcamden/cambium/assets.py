from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippcamden import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippcamden.cambium.schema import NJGPA_SCHEMA, NJSLA_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_file_asset

ssh_resource_key = "ssh_couchdrop"
remote_dir_regex_prefix = f"/data-team/{CODE_LOCATION}/cambium"
key_prefix = [CODE_LOCATION, "cambium"]

# The district code is hardcoded rather than matched with `\d+`: each region has
# its own Couchdrop folder, and build_sftp_file_asset raises on multiple
# matches, so a wildcard would break if the other district's file ever landed
# here.
DISTRICT_CODE = "1799"

# Feeds BOTH the filename regex alternation and the partition values, so the two
# cannot drift. Spring is the only administration Cambium sends; the fall tokens
# were Pearson-era cruft and never appeared in a Cambium file.
#
# This is not belt-and-braces. A token that matches the regex but is NOT a
# declared partition raises inside Dagster's resolve_run_requests, which
# processes every run request for the tick in one pass — so the whole tick fails,
# the cursor is not persisted on FAILURE, the file is re-listed forever, and all
# six of this region's Couchdrop assets stall until a redeploy. Sharing the list
# makes an unknown token simply not match, which skips the file and leaves the
# rest of the sensor working.
ADMINISTRATIONS = ["Spring"]

# Closed list for the same reason ADMINISTRATIONS is one, and shared with the
# filename regex the same way. An unbounded \d{4} captures any year, including
# one that is not a declared partition -- and an undeclared partition key raises
# inside resolve_run_requests, failing the whole tick and stalling every
# Couchdrop asset in this region. Bounded, an unexpected year fails to MATCH
# instead, which skips the file and leaves the rest of the sensor working.
#
# Not named fiscal_year: this is the 4-digit year as it appears in the filename,
# while academic year comes from the file's own assessment_year field. The range
# covers the value whether Cambium means calendar year or school-year-end year.
# Range end is exclusive: results for an academic year land in the NEXT fiscal
# year, so fiscal_year itself has no results yet.
ADMINISTRATION_YEARS = [
    str(year) for year in range(2026, CURRENT_FISCAL_YEAR.fiscal_year)
]

PARTITIONS_DEF = MultiPartitionsDefinition(
    {
        "administration_year": StaticPartitionsDefinition(ADMINISTRATION_YEARS),
        "administration": StaticPartitionsDefinition(ADMINISTRATIONS),
    }
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

FILENAME_REGEX_PREFIX = (
    rf"(?P<administration_year>{'|'.join(ADMINISTRATION_YEARS)})"
    rf"_(?P<administration>{'|'.join(ADMINISTRATIONS)})"
    rf"_{DISTRICT_CODE}_District_Summative_Record_File"
)

njgpa = build_sftp_file_asset(
    asset_key=[*key_prefix, "njgpa"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njgpa",
    remote_file_regex=rf"{FILENAME_REGEX_PREFIX}_GPA\.csv",
    avro_schema=NJGPA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=PARTITIONS_DEF,
)

njsla = build_sftp_file_asset(
    asset_key=[*key_prefix, "njsla"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njsla",
    remote_file_regex=rf"{FILENAME_REGEX_PREFIX}{UNKNOWN_FILE_SUFFIX}\.csv",
    avro_schema=NJSLA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=PARTITIONS_DEF,
)

# Shares NJSLA_SCHEMA with njsla, the way the two Pearson assets share theirs.
# Cambium has sent neither file, so there is no evidence the science layout
# differs, and one stub is one place to correct when the files arrive.
njsla_science = build_sftp_file_asset(
    asset_key=[*key_prefix, "njsla_science"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njsla_science",
    remote_file_regex=rf"{FILENAME_REGEX_PREFIX}{UNKNOWN_FILE_SUFFIX}\.csv",
    avro_schema=NJSLA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=PARTITIONS_DEF,
)

assets = [
    njgpa,
    njsla,
    njsla_science,
]
