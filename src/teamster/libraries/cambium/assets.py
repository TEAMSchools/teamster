from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

# Spring is the only administration Cambium sends. The fall tokens were
# Pearson-era cruft and never appeared in a Cambium file.
#
# Closed list, not an open `\w+`. A token that matches the filename regex but is
# NOT a declared partition raises inside Dagster's resolve_run_requests, which
# processes every run request for a tick in one pass -- so the whole tick fails,
# the cursor is not persisted on FAILURE, the file is re-listed forever, and
# every one of that region's Couchdrop assets stalls until a redeploy. Bounded,
# an unexpected token fails to MATCH instead, which skips the file and leaves
# the rest of the sensor working.
ADMINISTRATIONS = ["Spring"]

# Not named fiscal_year: this is the 4-digit year as it appears in the filename,
# while academic year comes from the file's own assessment_year field. The range
# covers the value whether Cambium means calendar year or school-year-end year.
# Range start is the first Cambium administration. Range end is exclusive:
# results for an academic year land in the NEXT fiscal year, so the current
# fiscal year itself has no results yet.
FIRST_ADMINISTRATION_YEAR = 2026


def build_partitions_def(current_fiscal_year: int) -> MultiPartitionsDefinition:
    """Build the partitions definition every Cambium summative feed shares.

    Args:
        current_fiscal_year: the code location's `CURRENT_FISCAL_YEAR.fiscal_year`.
    """
    return MultiPartitionsDefinition(
        {
            "administration_year": StaticPartitionsDefinition(
                [
                    str(year)
                    for year in range(FIRST_ADMINISTRATION_YEAR, current_fiscal_year)
                ]
            ),
            "administration": StaticPartitionsDefinition(ADMINISTRATIONS),
        }
    )


def build_remote_file_regex(
    partitions_def: MultiPartitionsDefinition,
    district_code: str,
    filename_suffix_regex: str,
) -> str:
    r"""Compose a Cambium summative record filename regex from its partitions.

    The alternations are read back off `partitions_def` rather than from a
    parallel list, so a filename this regex matches always captures a DECLARED
    partition key. That invariant used to rest on two module constants being
    edited together in each code location; here it holds by construction.

    Args:
        partitions_def: the asset's own partitions definition, from
            `build_partitions_def`.
        district_code: the region's 4-digit NJ district code, hardcoded rather
            than matched with `\d+` because each region has its own Couchdrop
            folder and `build_sftp_file_asset` raises on multiple matches.
        filename_suffix_regex: the fragment between `Record_File` and `.csv`.
            NJGPA's is the literal `_GPA`. NJSLA has sent no file yet, so its
            suffix is an optional group -- see the call site.
    """
    dimensions = {
        d.name: d.partitions_def.get_partition_keys()
        for d in partitions_def.partitions_defs
    }

    def alternation(dimension: str) -> str:
        # Longest first, so a token that is a prefix of another does not shadow
        # it. Moot while ADMINISTRATIONS holds one value, but the Pearson-era
        # tokens included both `Fall` and `FallBlock`, and `Fall|FallBlock`
        # matches `Fall` and leaves `Block` to fail against the next literal.
        return "|".join(sorted(dimensions[dimension], key=len, reverse=True))

    return (
        rf"(?P<administration_year>{alternation('administration_year')})"
        rf"_(?P<administration>{alternation('administration')})"
        rf"_{district_code}_District_Summative_Record_File{filename_suffix_regex}"
        r"\.csv"
    )
