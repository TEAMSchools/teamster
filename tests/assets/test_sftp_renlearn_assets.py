import random

from dagster import EnvVar, TextMetadataValue, _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.libraries.core.resources import get_io_manager_gcs_avro
from teamster.libraries.ssh.resources import SSHResource

SSH_RENLEARN_KIPPNJ = SSHResource(
    remote_host="sftp.renaissance.com",
    username=EnvVar("RENLEARN_SFTP_USERNAME_KIPPNJ"),
    password=EnvVar("RENLEARN_SFTP_PASSWORD_KIPPNJ"),
)

SSH_RENLEARN_KIPPMIAMI = SSHResource(
    remote_host="sftp.renaissance.com",
    username=EnvVar("RENLEARN_SFTP_USERNAME_KIPPMIAMI"),
    password=EnvVar("RENLEARN_SFTP_PASSWORD_KIPPMIAMI"),
)


def _test_asset(asset, ssh_resource: dict, partition_key=None, instance=None):
    if partition_key is not None:
        pass
    elif asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys(
            dynamic_partitions_store=instance
        )

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    else:
        partition_key = None

    result = materialize(
        assets=[asset],
        instance=instance,
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            **ssh_resource,
        },
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]

    event_specific_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = _check.inst(
        event_specific_data.materialization.metadata["records"].value, int
    )

    assert records > 0

    extras = _check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )

    assert extras.text == ""


def test_renlearn_accelerated_reader_kippnj():
    from teamster.code_locations.kippnewark.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "accelerated_reader"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPNJ})


def test_renlearn_accelerated_reader_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "accelerated_reader"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPMIAMI})


def test_renlearn_star_kippnj():
    from teamster.code_locations.kippnewark.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "star"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPNJ})


def test_renlearn_star_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "star"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPMIAMI})


def test_renlearn_star_skill_area_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "star_skill_area"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPMIAMI})


def test_renlearn_star_dashboard_standards_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "star_dashboard_standards"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPMIAMI})


def test_renlearn_fast_star_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "fast_star"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_renlearn": SSH_RENLEARN_KIPPMIAMI})
