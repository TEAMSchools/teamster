import pendulum
from dagster import EnvVar, build_resources
from fastavro import block_reader
from sqlalchemy import literal_column, select, table, text

from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHConfigurableResource

TEST_ASSETS = [
    {"asset_name": "gen"},
    {
        "asset_name": "schools",
        "partition_column": "transaction_date",
        "partition_key": "1970-01-01T00:00:00-00:00",
    },
    {
        "asset_name": "codeset",
        "partition_column": "whenmodified",
        "partition_key": "1970-01-01T00:00:00-00:00",
    },
]


def test_resource():
    with build_resources(
        resources={
            "ssh_powerschool": SSHConfigurableResource(
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
        ssh_powerschool: SSHConfigurableResource = resources.ssh_powerschool
        db_powerschool: OracleResource = resources.db_powerschool

        try:
            ssh_tunnel = ssh_powerschool.get_tunnel(remote_port=1521, local_port=1521)

            ssh_tunnel.start()

            for asset in TEST_ASSETS:
                partition_key = asset.get("partition_key")

                if partition_key is None:
                    constructed_where = ""
                elif partition_key == pendulum.from_timestamp(0).to_iso8601_string():
                    constructed_where = ""
                else:
                    window_start = pendulum.from_format(
                        string=partition_key, fmt="YYYY-MM-DDTHH:mm:ssZ"
                    )

                    window_start_fmt = window_start.format("YYYY-MM-DDTHH:mm:ss.SSSSSS")

                    constructed_where = (
                        f"{asset.get('partition_column')} >= "
                        f"TO_TIMESTAMP('{window_start_fmt}', "
                        "'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
                    )

                sql = (
                    select(
                        *[
                            literal_column(col)
                            for col in asset.get("select_columns", "*")
                        ]
                    )
                    .select_from(table(asset["asset_name"]))
                    .where(text(constructed_where))
                )

                file_path = db_powerschool.engine.execute_query(
                    query=sql, partition_size=100000, output_format="avro"
                )

                try:
                    with file_path.open(mode="rb") as f:
                        num_records = sum(
                            block.num_records for block in block_reader(f)
                        )
                except FileNotFoundError:
                    num_records = 0

                if num_records > 0:
                    print(file_path)
                    print(num_records)
        finally:
            ssh_tunnel.stop()
