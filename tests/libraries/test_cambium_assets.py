import re

import pytest
from dagster import AssetsDefinition, MultiPartitionsDefinition

from teamster.code_locations.kippcamden.cambium.assets import njgpa as camden_njgpa
from teamster.code_locations.kippnewark.cambium.assets import njgpa as newark_njgpa

# district code embedded in each region's filename
ASSETS = [(newark_njgpa, "7325"), (camden_njgpa, "1799")]


def _file_regex(asset: AssetsDefinition) -> re.Pattern:
    metadata = asset.metadata_by_key[asset.key]

    value = metadata["remote_file_regex"]

    return re.compile(getattr(value, "value", value))


def _declared(asset: AssetsDefinition) -> dict[str, list[str]]:
    partitions_def = asset.partitions_def

    assert isinstance(partitions_def, MultiPartitionsDefinition)

    return {
        d.name: list(d.partitions_def.get_partition_keys())
        for d in partitions_def.partitions_defs
    }


@pytest.mark.parametrize(("asset", "district_code"), ASSETS)
def test_every_matchable_filename_yields_a_declared_partition(asset, district_code):
    # The invariant both shared lists exist to hold: a filename the regex
    # matches must capture a partition key that is DECLARED. An undeclared key
    # raises inside resolve_run_requests, which processes every run request for
    # a tick in one pass -- so the whole tick fails, the cursor is not persisted,
    # and every Couchdrop asset in the region stalls until a redeploy.
    pattern = _file_regex(asset)
    declared = _declared(asset)

    for year in declared["administration_year"]:
        for season in declared["administration"]:
            filename = (
                f"{year}_{season}_{district_code}"
                "_District_Summative_Record_File_GPA.csv"
            )

            match = pattern.match(filename)

            assert match is not None, f"{filename} does not match its own regex"

            for dimension, captured in match.groupdict().items():
                assert captured in declared[dimension], (
                    f"{filename} captures {dimension}={captured},"
                    " which is not a declared partition"
                )


@pytest.mark.parametrize(("asset", "district_code"), ASSETS)
def test_undeclared_tokens_do_not_match(asset, district_code):
    # The other half of the invariant: an unexpected token must fail to MATCH,
    # which skips the file and leaves the rest of the sensor working, rather
    # than matching and producing an undeclared partition key.
    pattern = _file_regex(asset)
    declared = _declared(asset)

    known_year = declared["administration_year"][0]
    known_season = declared["administration"][0]

    for year, season in [
        ("2099", known_season),  # year outside the declared range
        (known_year, "Autumn"),  # season Cambium has never sent
    ]:
        filename = (
            f"{year}_{season}_{district_code}_District_Summative_Record_File_GPA.csv"
        )

        assert pattern.match(filename) is None, (
            f"{filename} matches the regex but {year}/{season} is not declared"
        )
