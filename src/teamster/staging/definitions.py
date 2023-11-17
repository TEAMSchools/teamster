from dagster import Definitions, EnvVar, load_assets_from_modules
from dagster_gcp import GCSResource

from teamster.core.google.io.resources import gcs_io_manager
from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHResource
from teamster.staging import CODE_LOCATION, GCS_PROJECT_NAME, powerschool

resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    assets=[
        *load_assets_from_modules(modules=[powerschool]),
    ],
    resources={
        "gcs": GCSResource(project=GCS_PROJECT_NAME),
        "io_manager_gcs_avro": gcs_io_manager.configured(
            config_or_config_fn={
                "gcs_bucket": f"teamster-{CODE_LOCATION}",
                "io_format": "avro",
            }
        ),
        "io_manager_gcs_file": gcs_io_manager.configured(
            config_or_config_fn={
                "gcs_bucket": f"teamster-{CODE_LOCATION}",
                "io_format": "filepath",
            }
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
