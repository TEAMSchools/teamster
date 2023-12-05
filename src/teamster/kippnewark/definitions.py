from dagster import Definitions, EnvVar, load_assets_from_modules
from dagster_dbt import DbtCliResource
from dagster_gcp import BigQueryResource, GCSResource
from dagster_k8s import k8s_job_executor

from teamster import GCS_PROJECT_NAME
from teamster.core.deanslist.resources import DeansListResource
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHResource
from teamster.kippnewark import (
    CODE_LOCATION,
    datagun,
    dbt,
    deanslist,
    edplan,
    iready,
    pearson,
    powerschool,
    renlearn,
    titan,
)

GCS_RESOURCE = GCSResource(project=GCS_PROJECT_NAME)

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(
        modules=[
            datagun,
            dbt,
            deanslist,
            edplan,
            iready,
            pearson,
            powerschool,
            renlearn,
            titan,
        ],
    ),
    jobs=[*datagun.jobs, *deanslist.jobs],
    schedules=[
        *datagun.schedules,
        *dbt.schedules,
        *deanslist.schedules,
        *powerschool.schedules,
    ],
    sensors=[
        *edplan.sensors,
        *iready.sensors,
        *powerschool.sensors,
        *renlearn.sensors,
        *titan.sensors,
    ],
    resources={
        "gcs": GCS_RESOURCE,
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
                password=EnvVar("KIPPNEWARK_PS_DB_PASSWORD"),
            ),
            version="19.0.0.0.0",
            prefetchrows=100000,
            arraysize=100000,
        ),
        "deanslist": DeansListResource(
            subdomain="kippnj",
            api_key_map="/etc/secret-volume/deanslist_api_key_map_yaml",
        ),
        "ssh_couchdrop": SSHResource(
            remote_host="kipptaf.couchdrop.io",
            username=EnvVar("COUCHDROP_SFTP_USERNAME"),
            password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
        ),
        "ssh_edplan": SSHResource(
            remote_host="secureftp.easyiep.com",
            username=EnvVar("KIPPNEWARK_EDPLAN_SFTP_USERNAME"),
            password=EnvVar("KIPPNEWARK_EDPLAN_SFTP_PASSWORD"),
        ),
        "ssh_iready": SSHResource(
            remote_host="prod-sftp-1.aws.cainc.com",
            username=EnvVar("IREADY_SFTP_USERNAME"),
            password=EnvVar("IREADY_SFTP_PASSWORD"),
        ),
        "ssh_powerschool": SSHResource(
            remote_host="psteam.kippnj.org",
            remote_port=EnvVar("KIPPNEWARK_PS_SSH_PORT").get_value(),
            username=EnvVar("KIPPNEWARK_PS_SSH_USERNAME"),
            password=EnvVar("KIPPNEWARK_PS_SSH_PASSWORD"),
            tunnel_remote_host=EnvVar("KIPPNEWARK_PS_SSH_REMOTE_BIND_HOST"),
        ),
        "ssh_renlearn": SSHResource(
            remote_host="sftp.renaissance.com",
            username=EnvVar("KIPPNJ_RENLEARN_SFTP_USERNAME"),
            password=EnvVar("KIPPNJ_RENLEARN_SFTP_PASSWORD"),
        ),
        "ssh_titan": SSHResource(
            remote_host="sftp.titank12.com",
            username=EnvVar("KIPPNEWARK_TITAN_SFTP_USERNAME"),
            password=EnvVar("KIPPNEWARK_TITAN_SFTP_PASSWORD"),
        ),
    },
)
