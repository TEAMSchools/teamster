from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager
from dagster_gcp.gcs.resources import gcs_resource

from teamster.core.powerschool.graphs.api import run_queries
from teamster.core.resources.google import gcs_file_manager
from teamster.core.resources.powerschool import powerschool_api

powerschool_api_extract = run_queries.to_job(
    name="powerschool_extract",
    resource_defs={
        "powerschool": powerschool_api,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config=config_from_files(
        [
            "src/teamster/core/config/google/resource.yaml",
            "src/teamster/core/config/powerschool/api/resource.yaml",
            "src/teamster/core/config/powerschool/api/query-test.yaml",
        ]
    ),
)

__all__ = ["powerschool_api_extract"]
