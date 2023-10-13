import random

from dagster_gcp import GCSResource

from dagster import EnvVar, config_from_files, materialize
from teamster.core.google.io.resources import gcs_io_manager
from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.staging import GCS_PROJECT_NAME


def _test_assets(assets, ssh_resource):
    for asset in assets:
        partition_keys = asset.partitions_def.get_partition_keys()

        result = materialize(
            assets=[asset],
            partition_key=partition_keys[
                random.randint(a=0, b=(len(partition_keys) - 1))
            ],
            resources={
                "gcs": GCSResource(project=GCS_PROJECT_NAME),
                "io_manager_gcs_avro": gcs_io_manager.configured(
                    config_from_files(
                        ["src/teamster/staging/config/resources/io_avro.yaml"]
                    )
                ),
                **ssh_resource,
            },
        )

        assert result.success


def test_assets_renlearn():
    from teamster.kippmiami.renlearn import assets

    _test_assets(
        assets=assets,
        ssh_resource={
            "ssh_renlearn": SSHConfigurableResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
                password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
            )
        },
    )

    from teamster.kippnewark.renlearn import assets

    _test_assets(
        assets=assets,
        ssh_resource={
            "ssh_renlearn": SSHConfigurableResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar("KIPPNJ_RENLEARN_SFTP_USERNAME"),
                password=EnvVar("KIPPNJ_RENLEARN_SFTP_PASSWORD"),
            )
        },
    )


def test_assets_fldoe():
    from teamster.kippmiami.fldoe import assets

    _test_assets(
        assets=assets,
        ssh_resource={
            "ssh_couchdrop": SSHConfigurableResource(
                remote_host="kipptaf.couchdrop.io",
                username=EnvVar("COUCHDROP_SFTP_USERNAME"),
                password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
            ),
        },
    )


def test_assets_iready():
    from teamster.kippmiami.iready import assets

    ssh_iready = SSHConfigurableResource(
        remote_host="prod-sftp-1.aws.cainc.com",
        username=EnvVar("IREADY_SFTP_USERNAME"),
        password=EnvVar("IREADY_SFTP_PASSWORD"),
    )

    _test_assets(assets=assets, ssh_resource={"ssh_iready": ssh_iready})

    from teamster.kippnewark.iready import assets

    _test_assets(assets=assets, ssh_resource={"ssh_iready": ssh_iready})
