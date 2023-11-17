import pendulum
from dagster import EnvVar, build_op_context, build_resources
from dagster_ssh import SSHResource
from fastavro import block_reader
from sqlalchemy import literal_column, select, table, text

from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource

with build_resources(
    resources={
        "ssh_powerschool": SSHResource(
            remote_host="teamacademy.clgpstest.com",
            remote_port=EnvVar("STAGING_PS_SSH_PORT"),
            username=EnvVar("STAGING_PS_SSH_USERNAME"),
            password=EnvVar("STAGING_PS_SSH_PASSWORD"),
            tunnel_remote_host=EnvVar("STAGING_PS_SSH_REMOTE_BIND_HOST"),
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
    }
) as resources:
    SSH_POWERSCHOOL: SSHResource = resources.ssh_powerschool
    DB_POWERSCHOOL: OracleResource = resources.db_powerschool


def _test(asset_name, partition_column=None, partition_key=None, select_columns="*"):
    context = build_op_context(partition_key=partition_key)

    context.log.info((asset_name, partition_column, partition_key, select_columns))

    # now = pendulum.now()

    if not context.has_partition_key:
        constructed_where = ""
    elif context.partition_key == pendulum.from_timestamp(0).to_iso8601_string():
        constructed_where = ""
    else:
        window_start = pendulum.from_format(
            string=context.partition_key, fmt="YYYY-MM-DDTHH:mm:ssZ"
        )

        window_start_fmt = window_start.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

        constructed_where = (
            f"{partition_column} >= "
            f"TO_TIMESTAMP('{window_start_fmt}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )

    sql = (
        select(*[literal_column(col) for col in select_columns])
        .select_from(table(asset_name))
        .where(text(constructed_where))
    )

    ssh_tunnel = SSH_POWERSCHOOL.get_tunnel(remote_port=1521, local_port=1521)

    try:
        context.log.info("Starting SSH tunnel")
        ssh_tunnel.start()

        file_path = DB_POWERSCHOOL.engine.execute_query(
            query=sql,
            partition_size=100000,
            output_format="avro",
            data_filepath="env/data.avro",
        )

        try:
            with file_path.open(mode="rb") as f:
                num_records = sum(block.num_records for block in block_reader(f))
        except FileNotFoundError:
            num_records = 0

        context.log.info(num_records)
    finally:
        context.log.info("Stopping SSH tunnel")
        ssh_tunnel.stop()


def test_assignmentsection():
    _test(asset_name="assignmentsection")


def test_storedgrades():
    _test(asset_name="storedgrades")


def test_schools():
    _test(asset_name="schools")
