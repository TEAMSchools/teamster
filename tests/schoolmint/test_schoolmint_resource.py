import json
import pathlib

from dagster import EnvVar, build_resources

from teamster.kipptaf.schoolmint.grow.resources import SchoolMintGrowResource

with build_resources(
    resources={
        "schoolmint_grow": SchoolMintGrowResource(
            client_id=EnvVar("SCHOOLMINT_GROW_CLIENT_ID"),
            client_secret=EnvVar("SCHOOLMINT_GROW_CLIENT_SECRET"),
            district_id=EnvVar("SCHOOLMINT_GROW_DISTRICT_ID"),
            api_response_limit=3200,
        )
    },
) as resources:
    SCHOOL_MINT_GROW: SchoolMintGrowResource = resources.schoolmint_grow


def _test(endpoint_name, **kwargs):
    response = SCHOOL_MINT_GROW.get(endpoint=endpoint_name, **kwargs)

    data = response["data"]

    filepath = pathlib.Path(
        f"env/schoolmint/grow/{endpoint_name.replace('/', '__')}.json"
    )

    filepath.parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj=data, fp=filepath.open(mode="w"))


def test_generic_tags_meetingtypes():
    _test("generic-tags/meetingtypes")


def test_schools():
    _test("schools")


def test_assignments():
    _test(endpoint_name="assignments", lastModified=1695600000.0)
