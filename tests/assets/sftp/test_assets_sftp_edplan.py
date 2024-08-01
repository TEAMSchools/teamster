import random

from dagster import EnvVar, materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.libraries.ssh.resources import SSHResource


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

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_edplan_kippcamden():
    from teamster.code_locations.kippcamden.edplan.assets import njsmart_powerschool

    _test_asset(
        asset=njsmart_powerschool,
        ssh_resource={
            "ssh_edplan": SSHResource(
                remote_host="secureftp.easyiep.com",
                username=EnvVar("EDPLAN_SFTP_USERNAME_KIPPCAMDEN"),
                password=EnvVar("EDPLAN_SFTP_PASSWORD_KIPPCAMDEN"),
            )
        },
    )


def test_edplan_kippnewark():
    from teamster.code_locations.kippnewark.edplan.assets import njsmart_powerschool

    _test_asset(
        asset=njsmart_powerschool,
        ssh_resource={
            "ssh_edplan": SSHResource(
                remote_host="secureftp.easyiep.com",
                username=EnvVar("EDPLAN_SFTP_USERNAME_KIPPNEWARK"),
                password=EnvVar("EDPLAN_SFTP_PASSWORD_KIPPNEWARK"),
            )
        },
    )
