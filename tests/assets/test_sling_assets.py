from dagster import materialize

from teamster.core.resources import get_ssh_resource_powerschool
from teamster.staging.resources import SLING_RESOURCE


def test_illuminate_table_assets():
    from teamster.staging.illuminate.assets import illuminate_table_assets

    materialize(assets=[illuminate_table_assets], resources={"sling": SLING_RESOURCE})


def test_powerschool_table_assets():
    from teamster.staging.powerschool.assets import powerschool_table_assets

    materialize(
        assets=[powerschool_table_assets],
        resources={
            "sling": SLING_RESOURCE,
            "ssh_powerschool": get_ssh_resource_powerschool(
                remote_host="psteam.kippnj.org"
            ),
        },
    )
