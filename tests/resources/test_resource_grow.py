from dagster import build_resources

from teamster.libraries.level_data.grow.resources import GrowResource


def _test_resource(method: str, *args, **kwargs):
    from teamster.code_locations.kipptaf.resources import GROW_RESOURCE

    with build_resources(resources={"grow": GROW_RESOURCE}) as resources:
        grow: GrowResource = resources.grow

    if method == "GET":
        response = grow.get(*args, **kwargs)
    elif method == "PUT":
        response = grow.put(*args, params={"district": grow.district_id})
    else:
        raise Exception

    return response


def test_users_single():
    response = _test_resource("GET", "users", "66e14104727cdd0011350d61")

    assert len(response["data"]) == 1


def test_users_all():
    response = _test_resource("GET", "users")

    user_ids = [user["_id"] for user in response["data"]]

    assert "6704d9fad037e00011d78610" in user_ids


def test_users_restore():
    _test_resource("PUT", "users", "5b5a06748e98130013e9e348", "restore")
