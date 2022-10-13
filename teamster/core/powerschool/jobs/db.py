from functools import reduce

import yaml
from dagster import config_from_files
from dagster_gcp.gcs import gcs_file_manager, gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor

from teamster.core.powerschool.graphs.db import resync, sync_standard
from teamster.core.resources.sqlalchemy import oracle
from teamster.core.resources.ssh import ssh_resource


# https://stackoverflow.com/a/7205107
def merge(a, b, path=None):
    "merges b into a"
    if path is None:
        path = []

    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)])
            elif isinstance(a[key], list) and isinstance(b[key], list):
                a[key] = a[key] + b[key]
            elif a[key] == b[key]:
                pass  # same leaf value
            else:
                raise Exception("Conflict at %s" % ".".join(path + [str(key)]))
        else:
            a[key] = b[key]
    return a


yaml_configs = []
for file_path in [
    "teamster/core/powerschool/config/db/sync-standard.yaml",
    "teamster/local/powerschool/config/db/sync-extensions.yaml",
]:
    with open(file=file_path, mode="r") as f:
        yaml_configs.append(yaml.safe_load(f.read()))

sync_standard_config = reduce(merge, yaml_configs)

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
