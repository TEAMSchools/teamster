import re

import pytest
from dagster import AssetsDefinition, MultiPartitionsDefinition

from teamster.code_locations.kippcamden.cambium.assets import njgpa as camden_njgpa
from teamster.code_locations.kippcamden.cambium.assets import njsla as camden_njsla
from teamster.code_locations.kippcamden.cambium.assets import (
    njsla_science as camden_njsla_science,
)
from teamster.code_locations.kippnewark.cambium.assets import njgpa as newark_njgpa
from teamster.code_locations.kippnewark.cambium.assets import njsla as newark_njsla
from teamster.code_locations.kippnewark.cambium.assets import (
    njsla_science as newark_njsla_science,
)

# The tail after `Record_File`. NJGPA's is verified against the real Cambium
# file. The NJSLA tails are the guesses the optional group has to accept,
# including the empty one for a file that carries no subject token at all.
NJGPA_TAILS = ["_GPA"]
NJSLA_TAILS = ["", "_SLA", "_ELA", "_MAT", "_SCI"]

# district code embedded in each region's filename
ASSETS = [
    (newark_njgpa, "7325", NJGPA_TAILS),
    (newark_njsla, "7325", NJSLA_TAILS),
    (newark_njsla_science, "7325", NJSLA_TAILS),
    (camden_njgpa, "1799", NJGPA_TAILS),
    (camden_njsla, "1799", NJSLA_TAILS),
    (camden_njsla_science, "1799", NJSLA_TAILS),
]

# Every ordered pair of feeds within one region. The njsla and njsla_science
# file regexes are permissive after `Record_File`, so only the directory keeps
# one feed's asset off another feed's file.
REGIONS = [
    ([newark_njgpa, newark_njsla, newark_njsla_science], "7325"),
    ([camden_njgpa, camden_njsla, camden_njsla_science], "1799"),
]

CROSS_FEED = [
    (asset, other, district_code)
    for assets, district_code in REGIONS
    for asset in assets
    for other in assets
    if asset is not other
]


def _metadata_value(asset: AssetsDefinition, key: str) -> str:
    value = asset.metadata_by_key[asset.key][key]

    return getattr(value, "value", value)


def _file_regex(asset: AssetsDefinition) -> re.Pattern:
    return re.compile(_metadata_value(asset=asset, key="remote_file_regex"))


def _composed_regex(asset: AssetsDefinition) -> re.Pattern:
    # Exactly how build_couchdrop_sftp_sensor composes the two metadata
    # regexes before matching a full Google Drive path.
    return re.compile(
        f"{_metadata_value(asset=asset, key='remote_dir_regex')}"
        f"/{_metadata_value(asset=asset, key='remote_file_regex')}"
    )


def _declared(asset: AssetsDefinition) -> dict[str, list[str]]:
    partitions_def = asset.partitions_def

    assert isinstance(partitions_def, MultiPartitionsDefinition)

    return {
        d.name: list(d.partitions_def.get_partition_keys())
        for d in partitions_def.partitions_defs
    }


def _filename(year: str, season: str, district_code: str, tail: str) -> str:
    return f"{year}_{season}_{district_code}_District_Summative_Record_File{tail}.csv"


@pytest.mark.parametrize(("asset", "district_code", "tails"), ASSETS)
def test_every_matchable_filename_yields_a_declared_partition(
    asset, district_code, tails
):
    # The invariant both shared lists exist to hold: a filename the regex
    # matches must capture a partition key that is DECLARED. An undeclared key
    # raises inside resolve_run_requests, which processes every run request for
    # a tick in one pass -- so the whole tick fails, the cursor is not persisted,
    # and every Couchdrop asset in the region stalls until a redeploy.
    pattern = _file_regex(asset)
    declared = _declared(asset)

    for year in declared["administration_year"]:
        for season in declared["administration"]:
            for tail in tails:
                filename = _filename(
                    year=year, season=season, district_code=district_code, tail=tail
                )

                match = pattern.match(filename)

                assert match is not None, f"{filename} does not match its own regex"

                for dimension, captured in match.groupdict().items():
                    assert captured in declared[dimension], (
                        f"{filename} captures {dimension}={captured},"
                        " which is not a declared partition"
                    )


@pytest.mark.parametrize(("asset", "district_code", "tails"), ASSETS)
def test_undeclared_tokens_do_not_match(asset, district_code, tails):
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
        filename = _filename(
            year=year, season=season, district_code=district_code, tail=tails[0]
        )

        assert pattern.match(filename) is None, (
            f"{filename} matches the regex but {year}/{season} is not declared"
        )


@pytest.mark.parametrize(("asset", "district_code", "tails"), ASSETS)
def test_the_other_districts_file_does_not_match(asset, district_code, tails):
    # Each region's Couchdrop folder is its own, but build_sftp_file_asset
    # raises on multiple matches, so a district code that is not this region's
    # must fail to match rather than being picked up.
    pattern = _file_regex(asset)
    declared = _declared(asset)

    other_district_code = "1799" if district_code == "7325" else "7325"

    filename = _filename(
        year=declared["administration_year"][0],
        season=declared["administration"][0],
        district_code=other_district_code,
        tail=tails[0],
    )

    assert pattern.match(filename) is None, (
        f"{filename} matches the {district_code} asset's regex"
    )


@pytest.mark.parametrize(("asset", "other", "district_code"), CROSS_FEED)
def test_one_feeds_asset_never_matches_another_feeds_file(asset, other, district_code):
    # The njsla and njsla_science file regexes end in an optional `(_\w+)?`
    # because Cambium has not sent either file and the subject token is a
    # guess. That permissiveness is only safe because the directory segment
    # scopes each asset to its own folder -- including `cambium/njsla` against
    # a path under `cambium/njsla_science`, which shares the njsla prefix.
    pattern = _composed_regex(asset)
    declared = _declared(asset)

    other_dir = _metadata_value(asset=other, key="remote_dir_regex")

    for tail in ["", "_GPA", "_SLA", "_ELA", "_MAT", "_SCI"]:
        path = f"{other_dir}/" + _filename(
            year=declared["administration_year"][0],
            season=declared["administration"][0],
            district_code=district_code,
            tail=tail,
        )

        assert pattern.match(path) is None, (
            f"{asset.key.to_user_string()} matches {path},"
            f" which belongs to {other.key.to_user_string()}"
        )
