import random

from dagster import EnvVar, materialize

from teamster.libraries.core.resources import get_io_manager_gcs_avro
from teamster.libraries.ssh.resources import SSHResource

SSH_TITAN_KIPPNEWARK = SSHResource(
    remote_host="sftp.titank12.com",
    username=EnvVar("TITAN_SFTP_USERNAME_KIPPNEWARK"),
    password=EnvVar("TITAN_SFTP_PASSWORD_KIPPNEWARK"),
)

SSH_TITAN_KIPPCAMDEN = SSHResource(
    remote_host="sftp.titank12.com",
    username=EnvVar("TITAN_SFTP_USERNAME_KIPPCAMDEN"),
    password=EnvVar("TITAN_SFTP_PASSWORD_KIPPCAMDEN"),
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

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_titan_person_data_kippnewark():
    from teamster.code_locations.kippnewark.titan.assets import person_data

    _test_asset(asset=person_data, ssh_resource={"ssh_titan": SSH_TITAN_KIPPNEWARK})


def test_titan_person_data_kippcamden():
    from teamster.code_locations.kippcamden.titan.assets import person_data

    _test_asset(
        asset=person_data,
        ssh_resource={"ssh_titan": SSH_TITAN_KIPPCAMDEN},
        partition_key="2023",
    )


def test_titan_income_form_data_kippnewark():
    from teamster.code_locations.kippnewark.titan.assets import income_form_data

    _test_asset(
        asset=income_form_data, ssh_resource={"ssh_titan": SSH_TITAN_KIPPNEWARK}
    )
