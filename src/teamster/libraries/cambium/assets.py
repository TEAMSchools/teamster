from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition


def build_partitions_def(
    current_fiscal_year: int,
    first_administration_year: int,
    administrations: list[str],
) -> MultiPartitionsDefinition:
    r"""Build a Cambium summative feed's partitions definition.

    Both dimensions are closed lists rather than an open `\d{4}` or `\w+`, and
    `build_remote_file_regex` builds the filename alternations from them. A
    token that MATCHES the regex but is not a declared partition raises inside
    Dagster's resolve_run_requests, which processes every run request for a tick
    in one pass -- so the whole tick fails, the cursor is not persisted, the file
    is re-listed forever, and every one of that region's Couchdrop assets stalls
    until a redeploy. Closed, an unexpected token fails to match instead, which
    skips the file and leaves the rest of the sensor working.

    Args:
        current_fiscal_year: the code location's `CURRENT_FISCAL_YEAR.fiscal_year`.
            The range ends EXCLUSIVE of it, because results for an academic year
            land in the NEXT fiscal year, so the current one has no results yet.
        first_administration_year: the 4-digit year of the region's first Cambium
            administration. Not a fiscal year: this is the year as it appears in
            the filename, while academic year comes from the file's own
            `assessment_year` field. A range covers the value whether Cambium
            means calendar year or school-year-end year.
        administrations: the season tokens Cambium puts in the filename.
    """
    return MultiPartitionsDefinition(
        {
            "administration_year": StaticPartitionsDefinition(
                [
                    str(year)
                    for year in range(first_administration_year, current_fiscal_year)
                ]
            ),
            "administration": StaticPartitionsDefinition(administrations),
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
    partition key. The invariant holds by construction, not by passing the same
    values to two functions.

    Args:
        partitions_def: the asset's own partitions definition, from
            `build_partitions_def`.
        district_code: the region's 4-digit NJ district code, hardcoded rather
            than matched with `\d+` because each region has its own Couchdrop
            folder and `build_sftp_file_asset` raises on multiple matches.
        filename_suffix_regex: the fragment between `Record_File` and `.csv`,
            a literal token where Cambium has delivered a file. A feed Cambium
            has never sent can pass a permissive group instead, which is safe
            because `remote_dir_regex` scopes each asset to its own folder and
            the sensor anchors its match at the start of the path. Two files
            landing in one folder still raise "Found multiple files matching"
            inside `build_sftp_file_asset`, which is the loud failure we want.
    """
    dimensions = {
        d.name: d.partitions_def.get_partition_keys()
        for d in partitions_def.partitions_defs
    }

    def alternation(dimension: str) -> str:
        # Longest first, so a token that is a prefix of another does not shadow
        # it. Moot while a region sends one season, but the Pearson-era tokens
        # included both `Fall` and `FallBlock`, and `Fall|FallBlock` matches
        # `Fall` and leaves `Block` to fail against the next literal.
        return "|".join(sorted(dimensions[dimension], key=len, reverse=True))

    return (
        rf"(?P<administration_year>{alternation('administration_year')})"
        rf"_(?P<administration>{alternation('administration')})"
        rf"_{district_code}_District_Summative_Record_File{filename_suffix_regex}"
        r"\.csv"
    )
