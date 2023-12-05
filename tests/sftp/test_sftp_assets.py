import random

from dagster import (
    DailyPartitionsDefinition,
    EnvVar,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    materialize,
)
from dagster_gcp import GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.ssh.resources import SSHResource
from teamster.core.utils.functions import get_avro_record_schema
from teamster.staging import LOCAL_TIMEZONE

SSH_IREADY = SSHResource(
    remote_host="prod-sftp-1.aws.cainc.com",
    username=EnvVar("IREADY_SFTP_USERNAME"),
    password=EnvVar("IREADY_SFTP_PASSWORD"),
)

SSH_COUCHDROP = SSHResource(
    remote_host="kipptaf.couchdrop.io",
    username=EnvVar("COUCHDROP_SFTP_USERNAME"),
    password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
)


def _test_asset(
    asset_key: list, asset_fields: dict, partitions_def, ssh_resource: dict, **kwargs
):
    asset_name = asset_key[-1]

    asset = build_sftp_asset(
        asset_key=["staging", *asset_key],
        ssh_resource_key=next(iter(ssh_resource.keys())),
        avro_schema=get_avro_record_schema(
            name=asset_name, fields=asset_fields[asset_name]
        ),
        partitions_def=partitions_def,
        **kwargs,
    )

    partition_keys = asset.partitions_def.get_partition_keys()

    result = materialize(
        assets=[asset],
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
        resources={
            "io_manager_gcs_avro": GCSIOManager(
                gcs=GCSResource(project=GCS_PROJECT_NAME),
                gcs_bucket="teamster-staging",
                object_type="avro",
            ),
            **ssh_resource,
        },
    )

    assert result.success


def test_assets_pearson_njgpa():
    from teamster.core.pearson.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["pearson", "njgpa"],
        asset_fields=ASSET_FIELDS,
        partitions_def=MultiPartitionsDefinition(
            {
                "fiscal_year": StaticPartitionsDefinition(["22", "23"]),
                "administration": StaticPartitionsDefinition(["spr", "fbk"]),
            }
        ),
        ssh_resource={"ssh_couchdrop": SSH_COUCHDROP},
    )


def test_assets_pearson_njsla():
    ...


def test_assets_pearson_njsla_science():
    ...


def test_assets_pearson_parcc():
    ...


def test_assets_renlearn_kippmiami():
    from teamster.kippmiami.renlearn import assets

    for asset in assets:
        _test_asset(
            asset=asset,
            ssh_resource={
                "ssh_renlearn": SSHResource(
                    remote_host="sftp.renaissance.com",
                    username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
                    password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
                )
            },
        )


def test_assets_renlearn_kippnewark():
    from teamster.kippnewark.renlearn import assets

    for asset in assets:
        _test_asset(
            asset=asset,
            ssh_resource={
                "ssh_renlearn": SSHResource(
                    remote_host="sftp.renaissance.com",
                    username=EnvVar("KIPPNJ_RENLEARN_SFTP_USERNAME"),
                    password=EnvVar("KIPPNJ_RENLEARN_SFTP_PASSWORD"),
                )
            },
        )


def test_assets_fldoe():
    from teamster.kippmiami.fldoe import assets

    for asset in assets:
        _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_assets_iready_kippmiami():
    from teamster.kippmiami.iready import assets

    for asset in assets:
        _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_assets_iready_kippnewark():
    from teamster.kippnewark.iready import assets

    for asset in assets:
        _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_assets_edplan():
    from teamster.core.edplan.schema import ASSET_FIELDS

    _test_asset(
        asset_key=["edplan", "njsmart_powerschool"],
        asset_fields=ASSET_FIELDS,
        partitions_def=DailyPartitionsDefinition(
            start_date="2023-05-08",
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%d",
            end_offset=1,
        ),
        ssh_resource={
            "ssh_edplan": SSHResource(
                remote_host="secureftp.easyiep.com",
                # username=EnvVar("KIPPCAMDEN_EDPLAN_SFTP_USERNAME"),
                # password=EnvVar("KIPPCAMDEN_EDPLAN_SFTP_PASSWORD"),
                username=EnvVar("KIPPNEWARK_EDPLAN_SFTP_USERNAME"),
                password=EnvVar("KIPPNEWARK_EDPLAN_SFTP_PASSWORD"),
            )
        },
        remote_dir="Reports",
        remote_file_regex=r"NJSMART-Power[Ss]chool\.txt",
    )


def test_assets_titan_kippcamden():
    from teamster.kippcamden.titan import assets

    for asset in assets:
        _test_asset(
            asset=asset,
            ssh_resource={
                "ssh_titan": SSHResource(
                    remote_host="sftp.titank12.com",
                    username=EnvVar("KIPPCAMDEN_TITAN_SFTP_USERNAME"),
                    password=EnvVar("KIPPCAMDEN_TITAN_SFTP_PASSWORD"),
                )
            },
        )


def test_assets_titan_kippnewark():
    from teamster.kippnewark.titan import assets

    for asset in assets:
        _test_asset(
            asset=asset,
            ssh_resource={
                "ssh_titan": SSHResource(
                    remote_host="sftp.titank12.com",
                    username=EnvVar("KIPPNEWARK_TITAN_SFTP_USERNAME"),
                    password=EnvVar("KIPPNEWARK_TITAN_SFTP_PASSWORD"),
                )
            },
        )


""" can't test dynamic partitions
def test_assets_achieve3k():
    from teamster.kipptaf.achieve3k import assets

    _test_asset(
        asset=assets,
        ssh_resource={
            "ssh_achieve3k": SSHResource(
                remote_host="xfer.achieve3000.com",
                username=EnvVar("ACHIEVE3K_SFTP_USERNAME"),
                password=EnvVar("ACHIEVE3K_SFTP_PASSWORD"),
            )
        },
    )


def test_assets_clever():
    from teamster.kipptaf.clever import assets

    _test_asset(
        asset=assets,
        ssh_resource={
            "ssh_clever_reports": SSHResource(
                remote_host="reports-sftp.clever.com",
                username=EnvVar("CLEVER_REPORTS_SFTP_USERNAME"),
                password=EnvVar("CLEVER_REPORTS_SFTP_PASSWORD"),
            )
        },
        partition_key="",
    )
"""
