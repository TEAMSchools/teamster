from dagster import AutoMaterializePolicy, Definitions, EnvVar, load_assets_from_modules
from dagster_dbt import DbtCliResource
from dagster_gcp import (
    BigQueryResource,
    ConfigurablePickledObjectGCSIOManager,
    GCSResource,
)
from dagster_k8s import k8s_job_executor

from teamster.core.deanslist.resources import DeansListResource
from teamster.core.google.io.resources import gcs_io_manager
from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHConfigurableResource

from . import (
    CODE_LOCATION,
    GCS_PROJECT_NAME,
    datagun,
    dbt,
    deanslist,
    fldoe,
    iready,
    powerschool,
    renlearn,
)

resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    executor=k8s_job_executor,
    assets=[
        *load_assets_from_modules(modules=[powerschool], group_name="powerschool"),
        *load_assets_from_modules(modules=[datagun], group_name="datagun"),
        *load_assets_from_modules(modules=[deanslist], group_name="deanslist"),
        *load_assets_from_modules(modules=[fldoe], group_name="fldoe"),
        *load_assets_from_modules(modules=[renlearn], group_name="renlearn"),
        *load_assets_from_modules(modules=[iready], group_name="iready"),
        *load_assets_from_modules(
            modules=[dbt], auto_materialize_policy=AutoMaterializePolicy.eager()
        ),
    ],
    jobs=[*datagun.jobs, *deanslist.jobs],
    schedules=[
        *datagun.schedules,
        *dbt.schedules,
        *powerschool.schedules,
        *deanslist.schedules,
    ],
    sensors=[*powerschool.sensors, *renlearn.sensors, *iready.sensors],
    resources={
        "io_manager": ConfigurablePickledObjectGCSIOManager(
            gcs=GCSResource(project=GCS_PROJECT_NAME), gcs_bucket="teamster-kippmiami"
        ),
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
        "gcs": GCSResource(project=GCS_PROJECT_NAME),
        "dbt_cli": DbtCliResource(project_dir=f"src/dbt/{CODE_LOCATION}"),
        "db_bigquery": BigQueryResource(project=GCS_PROJECT_NAME),
        "db_powerschool": OracleResource(
            engine=SqlAlchemyEngineResource(
                dialect="oracle",
                driver="oracledb",
                username="PSNAVIGATOR",
                host="localhost",
                database="PSPRODDB",
                port=1521,
                password=EnvVar("KIPPMIAMI_PS_DB_PASSWORD"),
            ),
            version="19.0.0.0.0",
            prefetchrows=100000,
            arraysize=100000,
        ),
        "deanslist": DeansListResource(
            subdomain="kippnj",
            api_key_map="/etc/secret-volume/deanslist_api_key_map_yaml",
        ),
        "ssh_couchdrop": SSHConfigurableResource(
            remote_host="kipptaf.couchdrop.io",
            username=EnvVar("COUCHDROP_SFTP_USERNAME"),
            password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
        ),
        "ssh_iready": SSHConfigurableResource(
            remote_host="prod-sftp-1.aws.cainc.com",
            username=EnvVar("IREADY_SFTP_USERNAME"),
            password=EnvVar("IREADY_SFTP_PASSWORD"),
        ),
        "ssh_powerschool": SSHConfigurableResource(
            remote_host="ps.kippmiami.org",
            remote_port=EnvVar("KIPPMIAMI_PS_SSH_PORT"),
            username=EnvVar("KIPPMIAMI_PS_SSH_USERNAME"),
            password=EnvVar("KIPPMIAMI_PS_SSH_PASSWORD"),
            tunnel_remote_host=EnvVar("KIPPMIAMI_PS_SSH_REMOTE_BIND_HOST"),
        ),
        "ssh_pythonanywhere": SSHConfigurableResource(
            remote_host="ssh.pythonanywhere.com",
            username=EnvVar("PYTHONANYWHERE_SFTP_USERNAME"),
            password=EnvVar("PYTHONANYWHERE_SFTP_PASSWORD"),
        ),
        "ssh_renlearn": SSHConfigurableResource(
            remote_host="sftp.renaissance.com",
            username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
            password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
        ),
    },
)
