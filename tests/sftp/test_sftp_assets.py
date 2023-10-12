import random

from dagster import EnvVar, config_from_files, materialize
from dagster_gcp import GCSResource

from teamster.core.google.io.resources import gcs_io_manager
from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.staging import CODE_LOCATION, GCS_PROJECT_NAME

resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"


def test_assets_renlearn_kippmiami():
    from teamster.kippmiami.renlearn import assets

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
                    config_from_files([f"{resource_config_dir}/io_avro.yaml"])
                ),
                "ssh_renlearn": SSHConfigurableResource(
                    remote_host="sftp.renaissance.com",
                    username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
                    password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
                ),
            },
        )

        assert result.success


def test_assets_fldoe_kippmiami():
    from teamster.kippmiami.fldoe import assets

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
                    config_from_files([f"{resource_config_dir}/io_avro.yaml"])
                ),
                "ssh_couchdrop": SSHConfigurableResource(
                    remote_host="kipptaf.couchdrop.io",
                    username=EnvVar("COUCHDROP_SFTP_USERNAME"),
                    password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
                ),
            },
        )

        assert result.success


def test_assets_iready_kippmiami():
    from teamster.kippmiami.iready import assets

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
                    config_from_files([f"{resource_config_dir}/io_avro.yaml"])
                ),
                "ssh_iready": SSHConfigurableResource(
                    remote_host="prod-sftp-1.aws.cainc.com",
                    username=EnvVar("IREADY_SFTP_USERNAME"),
                    password=EnvVar("IREADY_SFTP_PASSWORD"),
                ),
            },
        )

        assert result.success
