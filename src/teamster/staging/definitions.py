from dagster import AutoMaterializePolicy, Definitions, EnvVar, load_assets_from_modules
from dagster_dbt import DbtCliResource
from dagster_gcp import GCSPickleIOManager, GCSResource

from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.staging import CODE_LOCATION, GCS_PROJECT_NAME, dbt, powerschool

defs = Definitions(
    assets=[
        *load_assets_from_modules(
            modules=[dbt], auto_materialize_policy=AutoMaterializePolicy.eager()
        ),
        *load_assets_from_modules(modules=[powerschool]),
    ],
    resources={
        "io_manager_gcs_avro": GCSPickleIOManager(
            gcs=GCSResource(project=GCS_PROJECT_NAME),
            gcs_bucket=f"teamster-{CODE_LOCATION}",
        ),
        "io_manager_gcs_file": GCSPickleIOManager(
            gcs=GCSResource(project=GCS_PROJECT_NAME),
            gcs_bucket=f"teamster-{CODE_LOCATION}",
        ),
        "dbt_cli": DbtCliResource(project_dir=f"src/dbt/{CODE_LOCATION}"),
        "db_powerschool": OracleResource(
            engine=SqlAlchemyEngineResource(
                dialect="oracle",
                driver="oracledb",
                username="PSNAVIGATOR",
                host="localhost",
                database="PSPRODDB",
                port=1521,
                password=EnvVar("KIPPCAMDEN_PS_DB_PASSWORD"),
            ),
            version="19.0.0.0.0",
            prefetchrows=100000,
            arraysize=100000,
        ),
        "ssh_powerschool": SSHConfigurableResource(
            remote_host="pskcna.kippnj.org",
            remote_port=EnvVar("KIPPCAMDEN_PS_SSH_PORT"),
            username=EnvVar("KIPPCAMDEN_PS_SSH_USERNAME"),
            password=EnvVar("KIPPCAMDEN_PS_SSH_PASSWORD"),
            tunnel_remote_host=EnvVar("KIPPCAMDEN_PS_SSH_REMOTE_BIND_HOST"),
        ),
    },
)
