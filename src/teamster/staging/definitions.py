from dagster import (
    AutoMaterializePolicy,
    Definitions,
    EnvVar,
    config_from_files,
    load_assets_from_modules,
)
from dagster_dbt import DbtCliResource
from dagster_gcp import GCSResource

from teamster.core.google.io.resources import gcs_io_manager
from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.staging import CODE_LOCATION, GCS_PROJECT_NAME, dbt, fldoe, renlearn

resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    assets=[
        *load_assets_from_modules(
            modules=[dbt], auto_materialize_policy=AutoMaterializePolicy.eager()
        ),
        *load_assets_from_modules(modules=[fldoe]),
        *load_assets_from_modules(modules=[renlearn]),
    ],
    resources={
        "gcs": GCSResource(project=GCS_PROJECT_NAME),
        "io_manager_gcs_avro": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_avro.yaml"])
        ),
        "dbt_cli": DbtCliResource(project_dir=f"src/dbt/{CODE_LOCATION}"),
        "ssh_couchdrop": SSHConfigurableResource(
            remote_host="kipptaf.couchdrop.io",
            username=EnvVar("COUCHDROP_SFTP_USERNAME"),
            password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
        ),
        "ssh_renlearn": SSHConfigurableResource(
            remote_host="sftp.renaissance.com",
            username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
            password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
        ),
    },
)
