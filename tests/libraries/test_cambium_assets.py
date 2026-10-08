import re

import pytest
from dagster import (
    AssetsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
)

from teamster.code_locations.kippcamden.cambium.assets import njgpa as camden_njgpa
from teamster.code_locations.kippcamden.cambium.assets import njsla as camden_njsla
from teamster.code_locations.kippnewark.cambium.assets import njgpa as newark_njgpa
from teamster.code_locations.kippnewark.cambium.assets import njsla as newark_njsla
from teamster.code_locations.kipppaterson.cambium.assets import njsla as paterson_njsla
from teamster.libraries.cambium.assets import build_remote_file_regex
from teamster.libraries.sftp.assets import compose_regex

# (Couchdrop subfolder, tail after `Record_File`) for each file an asset reads,
# verified against the real Cambium files. The njsla asset reads the NJSLA and
# end-of-course files from their two folders.
NJGPA_FILES = [("njgpa", "_GPA")]
NJSLA_FILES = [("njsla", "_SLA"), ("eoc", "_SLA_EOC")]

# district code embedded in each region's filename
ASSETS = [
    (newark_njgpa, "kippnewark", "7325", NJGPA_FILES),
    (newark_njsla, "kippnewark", "7325", NJSLA_FILES),
    (camden_njgpa, "kippcamden", "1799", NJGPA_FILES),
    (camden_njsla, "kippcamden", "1799", NJSLA_FILES),
    (paterson_njsla, "kipppaterson", "7899", NJSLA_FILES),
]

DISTRICT_CODES = {district_code for _, _, district_code, _ in ASSETS}

# Every ordered pair of feeds within one region. Only the subfolder keeps one
# feed's asset off another feed's file.
CROSS_FEED = [
    (asset, other_files, code_location, district_code)
    for asset, code_location, district_code, _ in ASSETS
    for other, other_code_location, _, other_files in ASSETS
    if other_code_location == code_location and other is not asset
]


def _metadata_value(asset: AssetsDefinition, key: str) -> str:
    value = asset.metadata_by_key[asset.key][key]

    return getattr(value, "value", value)


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


def _path(code_location: str, folder: str, filename: str) -> str:
    return f"/data-team/{code_location}/cambium/{folder}/{filename}"


@pytest.mark.parametrize(("asset", "code_location", "district_code", "files"), ASSETS)
def test_every_matchable_filename_yields_a_declared_partition(
    asset, code_location, district_code, files
):
    # The invariant both shared lists exist to hold: a filename the regex
    # matches must capture a partition key that is DECLARED. An undeclared key
    # raises inside resolve_run_requests, which processes every run request for
    # a tick in one pass -- so the whole tick fails, the cursor is not persisted,
    # and every Couchdrop asset in the region stalls until a redeploy.
    pattern = _composed_regex(asset)
    declared = _declared(asset)

    for year in declared["administration_year"]:
        for season in declared["administration"]:
            for folder, tail in files:
                path = _path(
                    code_location=code_location,
                    folder=folder,
                    filename=_filename(
                        year=year, season=season, district_code=district_code, tail=tail
                    ),
                )

                match = pattern.match(path)

                assert match is not None, f"{path} does not match its own regex"

                for dimension, captured in match.groupdict().items():
                    assert captured in declared[dimension], (
                        f"{path} captures {dimension}={captured},"
                        " which is not a declared partition"
                    )


@pytest.mark.parametrize(("asset", "code_location", "district_code", "files"), ASSETS)
def test_the_run_time_regex_still_matches_every_file(
    asset, code_location, district_code, files
):
    # At run time the asset substitutes the partition key into the regexes with
    # compose_regex before searching the SFTP listing. The subfolder group is
    # not a named group, so it must survive that substitution intact.
    declared = _declared(asset)

    year = declared["administration_year"][0]
    season = declared["administration"][0]

    pattern = "/".join(
        compose_regex(
            regexp=_metadata_value(asset=asset, key=key),
            partition_key=MultiPartitionKey(
                {"administration_year": year, "administration": season}
            ),
        )
        for key in ["remote_dir_regex", "remote_file_regex"]
    )

    for folder, tail in files:
        path = _path(
            code_location=code_location,
            folder=folder,
            filename=_filename(
                year=year, season=season, district_code=district_code, tail=tail
            ),
        )

        assert re.search(pattern=pattern, string=path) is not None, (
            f"{path} does not match the run-time regex {pattern}"
        )


@pytest.mark.parametrize(("asset", "code_location", "district_code", "files"), ASSETS)
def test_undeclared_tokens_do_not_match(asset, code_location, district_code, files):
    # The other half of the invariant: an unexpected token must fail to MATCH,
    # which skips the file and leaves the rest of the sensor working, rather
    # than matching and producing an undeclared partition key.
    pattern = _composed_regex(asset)
    declared = _declared(asset)

    known_year = declared["administration_year"][0]
    known_season = declared["administration"][0]

    folder, tail = files[0]

    for year, season in [
        ("2099", known_season),  # year outside the declared range
        (known_year, "Autumn"),  # season Cambium has never sent
    ]:
        path = _path(
            code_location=code_location,
            folder=folder,
            filename=_filename(
                year=year, season=season, district_code=district_code, tail=tail
            ),
        )

        assert pattern.match(path) is None, (
            f"{path} matches the regex but {year}/{season} is not declared"
        )


@pytest.mark.parametrize(("asset", "code_location", "district_code", "files"), ASSETS)
def test_the_other_districts_file_does_not_match(
    asset, code_location, district_code, files
):
    # Each region's Couchdrop folder is its own, but a district code that is
    # not this region's must still fail to match rather than being picked up.
    pattern = _composed_regex(asset)
    declared = _declared(asset)

    for other_district_code in DISTRICT_CODES - {district_code}:
        for folder, tail in files:
            path = _path(
                code_location=code_location,
                folder=folder,
                filename=_filename(
                    year=declared["administration_year"][0],
                    season=declared["administration"][0],
                    district_code=other_district_code,
                    tail=tail,
                ),
            )

            assert pattern.match(path) is None, (
                f"{path} matches the {district_code} asset's regex"
            )


@pytest.mark.parametrize(
    ("asset", "other_files", "code_location", "district_code"), CROSS_FEED
)
def test_one_feeds_asset_never_matches_another_feeds_file(
    asset, other_files, code_location, district_code
):
    # A subject token this feed has never carried must still not pull in
    # another feed's file, so the subfolder -- not the filename tail -- is what
    # scopes each asset to its own files.
    pattern = _composed_regex(asset)
    declared = _declared(asset)

    for folder, _ in other_files:
        for tail in ["", "_GPA", "_SLA", "_SLA_EOC", "_ELA", "_MAT", "_SCI"]:
            path = _path(
                code_location=code_location,
                folder=folder,
                filename=_filename(
                    year=declared["administration_year"][0],
                    season=declared["administration"][0],
                    district_code=district_code,
                    tail=tail,
                ),
            )

            assert pattern.match(path) is None, (
                f"{asset.key.to_user_string()} matches {path}, which is another"
                " feed's file"
            )


def test_a_prefix_token_does_not_shadow_a_longer_one():
    # build_remote_file_regex reads its alternations off the partitions
    # definition, so the order is the generator's to get right. `Fall|FallBlock`
    # matches `Fall` and leaves `Block` to fail against the next literal, which
    # would skip a file that IS a declared partition. ADMINISTRATIONS holds one
    # value today, so nothing else exercises this.
    partitions_def = MultiPartitionsDefinition(
        {
            "administration_year": StaticPartitionsDefinition(["2026"]),
            "administration": StaticPartitionsDefinition(["Fall", "FallBlock"]),
        }
    )

    pattern = re.compile(
        build_remote_file_regex(
            partitions_def=partitions_def,
            district_code="7325",
            filename_suffix_regex=r"_GPA",
        )
    )

    for season in ["Fall", "FallBlock"]:
        filename = _filename(
            year="2026", season=season, district_code="7325", tail="_GPA"
        )

        match = pattern.match(filename)

        assert match is not None, f"{filename} does not match"
        assert match.group("administration") == season, (
            f"{filename} captured {match.group('administration')}, not {season}"
        )
