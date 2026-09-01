from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippnewark.cambium.schema import NJGPA_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_file_asset

ssh_resource_key = "ssh_couchdrop"
remote_dir_regex_prefix = f"/data-team/{CODE_LOCATION}/cambium"
key_prefix = [CODE_LOCATION, "cambium"]

# Feeds BOTH the filename regex alternation and the partition values, so the two
# cannot drift. Spring is verified from the files in hand; the rest are the fall
# tokens Pearson actually used (FallBlock in 2024, FALL in 2025).
#
# This is not belt-and-braces. A token that matches the regex but is NOT a
# declared partition raises inside Dagster's resolve_run_requests, which
# processes every run request for the tick in one pass — so the whole tick fails,
# the cursor is not persisted on FAILURE, the file is re-listed forever, and all
# six of this region's Couchdrop assets stall until a redeploy. Sharing the list
# makes an unknown token simply not match, which skips the file and leaves the
# rest of the sensor working.
ADMINISTRATIONS = ["Spring", "Fall", "FALL", "FallBlock"]

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
ADMINISTRATION_YEARS = [
    str(year) for year in range(2026, CURRENT_FISCAL_YEAR.fiscal_year + 1)
]

# The district code is hardcoded rather than matched with `\d+`: each region has
# its own Couchdrop folder, and build_sftp_file_asset raises on multiple
# matches, so a wildcard would break if the other district's file ever landed
# here.
njgpa = build_sftp_file_asset(
    asset_key=[*key_prefix, "njgpa"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njgpa",
    remote_file_regex=(
        rf"(?P<administration_year>{'|'.join(ADMINISTRATION_YEARS)})"
        # longest-first so FallBlock is not shadowed by Fall
        rf"_(?P<administration>{'|'.join(sorted(ADMINISTRATIONS, key=len, reverse=True))})"
        r"_7325_District_Summative_Record_File_GPA\.csv"
    ),
    avro_schema=NJGPA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=MultiPartitionsDefinition(
        {
            "administration_year": StaticPartitionsDefinition(ADMINISTRATION_YEARS),
            "administration": StaticPartitionsDefinition(ADMINISTRATIONS),
        }
    ),
)

assets = [
    njgpa,
]
