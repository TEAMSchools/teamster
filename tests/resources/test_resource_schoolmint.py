from dagster import build_resources

from teamster.code_locations.kipptaf.resources import SCHOOLMINT_GROW_RESOURCE
from teamster.libraries.schoolmint.grow.resources import SchoolMintGrowResource


def _test_resource(method: str, *args, **kwargs):
    with build_resources(
        resources={"schoolmint_grow": SCHOOLMINT_GROW_RESOURCE}
    ) as resources:
        schoolmint_grow: SchoolMintGrowResource = resources.schoolmint_grow

    if method == "GET":
        response = schoolmint_grow.get(*args, **kwargs)
    elif method == "PUT":
        response = schoolmint_grow.put(
            *args, params={"district": schoolmint_grow.district_id}
        )
    else:
        raise Exception

    return response


def test_users_single():
    response = _test_resource("GET", "users", "66e14104727cdd0011350d61")

    assert len(response["data"]) == 1


def test_users_all():
    response = _test_resource("GET", "users", limit=100)

    user_ids = [user["_id"] for user in response["data"]]

    assert "66e14104727cdd0011350d61" in user_ids


def test_users_restore():
    _test_resource("PUT", "users", "5b5a06748e98130013e9e348", "restore")
