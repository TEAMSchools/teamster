import random

from dagster import AssetsDefinition, EnvVar, materialize


def _test_asset(
    asset: AssetsDefinition,
    code_location: str,
    partition_key: str | None = None,
    instance=None,
):
    from teamster.core.resources import get_io_manager_gcs_avro
    from teamster.libraries.ssh.resources import SSHResource

    if partition_key is None and asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys(
            dynamic_partitions_store=instance
        )

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        instance=instance,
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "ssh_edplan": SSHResource(
                remote_host="secureftp.easyiep.com",
                remote_port=22,
                username=EnvVar(f"EDPLAN_SFTP_USERNAME_{code_location.upper()}"),
                password=EnvVar(f"EDPLAN_SFTP_PASSWORD_{code_location.upper()}"),
            ),
        },
    )

    assert result.success

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_edplan_kippcamden():
    from teamster.code_locations.kippcamden.edplan.assets import njsmart_powerschool

    _test_asset(asset=njsmart_powerschool, code_location="kippcamden")


def test_edplan_kippnewark():
    from teamster.code_locations.kippnewark.edplan.assets import njsmart_powerschool

    _test_asset(asset=njsmart_powerschool, code_location="kippnewark")
