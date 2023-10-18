import random

from dagster import EnvVar, materialize
from dagster_gcp import GCSPickleIOManager, GCSResource

from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.staging import GCS_PROJECT_NAME
from teamster.staging.powerschool.assets import (
    full_assets,
    transaction_date_partition_assets,
)


def _test_asset(asset, partition_key=None):
    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        resources={
            "io_manager_gcs_file": GCSPickleIOManager(
                gcs=GCSResource(project=GCS_PROJECT_NAME), gcs_bucket="teamster-staging"
            ),
            "db_powerschool": OracleResource(
                engine=SqlAlchemyEngineResource(
                    dialect="oracle",
                    driver="oracledb",
                    username="PSNAVIGATOR",
                    host="localhost",
                    database="PSPRODDB",
                    port=1521,
                    password=EnvVar("STAGING_PS_DB_PASSWORD"),
                ),
                version="19.0.0.0.0",
                prefetchrows=100000,
                arraysize=100000,
            ),
            "ssh_powerschool": SSHConfigurableResource(
                remote_host="teamacademy.clgpstest.com",
                remote_port=EnvVar("STAGING_PS_SSH_PORT"),
                username=EnvVar("STAGING_PS_SSH_USERNAME"),
                password=EnvVar("STAGING_PS_SSH_PASSWORD"),
                tunnel_remote_host=EnvVar("STAGING_PS_SSH_REMOTE_BIND_HOST"),
            ),
        },
    )

    assert result.success


def test_full_assets():
    for asset in full_assets:
        _test_asset(asset=asset)


def test_transaction_date_partition_assets():
    for asset in transaction_date_partition_assets:
        partition_keys = asset.partitions_def.get_partition_keys()

        _test_asset(
            asset=asset,
            partition_key=partition_keys[
                random.randint(a=0, b=(len(partition_keys) - 1))
            ],
        )
