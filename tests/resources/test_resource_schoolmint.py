from dagster import build_resources

from teamster.code_locations.kipptaf.resources import SCHOOLMINT_GROW_RESOURCE


def test_foo():
    with build_resources(resources={"smg": SCHOOLMINT_GROW_RESOURCE}) as resources:
        resources.smg.get("users", "66b347636a5f36001143fe85")
