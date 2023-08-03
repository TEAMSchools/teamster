import json

from dagster import EnvVar, build_resources

from teamster.core.schoolmint.grow.resources import SchoolMintGrowResource

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


def _test(endpoint_name):
    data = []

    for params in [True, None]:
        response = SCHOOL_MINT_GROW.get(endpoint=endpoint_name, archived=params)

        data.extend(response["data"])

    with open(file=f"env/{endpoint_name.replace('/', '__')}.json", mode="w") as fp:
        json.dump(obj=data, fp=fp)


def test_generic_tags_meetingtypes():
    _test("generic-tags/meetingtypes")
