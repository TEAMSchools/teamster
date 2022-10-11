import yaml
from dagster import config_from_files
from dagster_gcp.gcs import gcs_file_manager, gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor

from teamster.core.powerschool.graphs.db import resync, sync_standard
from teamster.core.resources.sqlalchemy import oracle
from teamster.core.resources.ssh import ssh_resource

sync_standard_config = {"ops": {"config": {"queries": []}}}
for file_path in [
    "teamster/core/powerschool/config/db/sync-standard.yaml",
    "teamster/local/powerschool/config/db/sync-extensions.yaml",
]:
    with open(file=file_path, mode="r") as f:
        yaml_config = yaml.safe_load(f.read())
    queries = yaml_config["ops"]["config"]["queries"]
    sync_standard_config["ops"]["config"]["queries"].extend(queries)

powerschool_db_sync_std = sync_standard.to_job(
    name="powerschool_db_sync_std",
    executor_def=k8s_job_executor,
    resource_defs={
        "db": oracle,
        "ssh": ssh_resource,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config={
        **config_from_files(
            [
                "teamster/core/resources/config/google.yaml",
                "teamster/core/powerschool/config/db/resource.yaml",
                "teamster/core/powerschool/config/db/sync.yaml",
            ]
        ),
        **sync_standard_config,
    },
)

powerschool_db_resync = resync.to_job(
    name="powerschool_db_resync",
    executor_def=k8s_job_executor,
    resource_defs={
        "db": oracle,
        "ssh": ssh_resource,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config=config_from_files(
        [
            "teamster/core/resources/config/google.yaml",
            "teamster/core/powerschool/config/db/resource.yaml",
            "teamster/core/powerschool/config/db/resync.yaml",
            "teamster/local/powerschool/config/db/sync-resync.yaml",
        ]
    ),
)


__all__ = ["powerschool_db_sync_std", "powerschool_db_resync"]
