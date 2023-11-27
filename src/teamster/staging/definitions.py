from dagster import Definitions, EnvVar, load_assets_from_modules
from dagster_gcp import GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHResource
from teamster.staging import CODE_LOCATION, powerschool

GCS_RESOURCE = GCSResource(project=GCS_PROJECT_NAME)

defs = Definitions(
    assets=[
        *load_assets_from_modules(modules=[powerschool]),
    ],
    resources={
        "io_manager": GCSIOManager(
            gcs=GCS_RESOURCE,
            gcs_bucket=f"teamster-{CODE_LOCATION}",
            object_type="pickle",
        ),
        "io_manager_gcs_avro": GCSIOManager(
            gcs=GCS_RESOURCE, gcs_bucket=f"teamster-{CODE_LOCATION}", object_type="avro"
        ),
        "io_manager_gcs_file": GCSIOManager(
            gcs=GCS_RESOURCE, gcs_bucket=f"teamster-{CODE_LOCATION}", object_type="file"
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
        "ssh_powerschool": SSHResource(
            remote_host="psteam.kippnj.org",
            remote_port=EnvVar("STAGING_PS_SSH_PORT").get_value(),
            username=EnvVar("STAGING_PS_SSH_USERNAME"),
            password=EnvVar("STAGING_PS_SSH_PASSWORD"),
            tunnel_remote_host=EnvVar("STAGING_PS_SSH_REMOTE_BIND_HOST"),
        ),
    },
)
