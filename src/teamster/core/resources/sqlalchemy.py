import json
import pathlib
import sys
from datetime import datetime

import oracledb
from dagster import Field, IntSource, Permissive, StringSource, resource
from dagster._utils.merger import merge_dicts
from fastavro import parse_schema, writer
from sqlalchemy.engine import URL, create_engine

from teamster.core.utils.classes import CustomJSONEncoder

sys.modules["cx_Oracle"] = oracledb


class SqlAlchemyEngine(object):
    def __init__(self, dialect, driver, logger, **kwargs):
        self.log = logger

        engine_keys = ["arraysize", "connect_args"]
        engine_kwargs = {k: v for k, v in kwargs.items() if k in engine_keys}
        url_kwargs = {k: v for k, v in kwargs.items() if k not in engine_keys}

        self.connection_url = URL.create(drivername=f"{dialect}+{driver}", **url_kwargs)
        self.engine = create_engine(url=self.connection_url, **engine_kwargs)

    def execute_query(self, query, partition_size, output, connect_kwargs={}):
        self.log.debug("Opening connection to engine")
        with self.engine.connect(**connect_kwargs) as conn:
            self.log.info(f"Executing query:\n{query}")
            result = conn.execute(statement=query)

            try:
                self.log.debug([col for col in result.cursor.description])
                self.log.debug(result.context.compiled.statement.columns)
            except Exception:
                pass

            if output is None:
                pass
            else:
                self.log.debug("Staging result mappings")
                result = result.mappings()

            self.log.debug("Partitioning results")
            partitions = result.partitions(size=partition_size)

            if output in ["dict", "json"] or output is None:
                self.log.debug("Retrieving rows from all partitions")
                pt_rows = [rows for pt in partitions for rows in pt]

                self.log.debug("Unpacking partition rows")
                output_data = [
                    dict(row) if output in ["dict", "json"] else row for row in pt_rows
                ]

                del pt_rows
                self.log.info(f"Retrieved {len(output_data)} rows")
            elif output == "avro":
                data_dir = pathlib.Path("data").absolute()
                data_dir.mkdir(parents=True, exist_ok=True)

                now_timestamp = str(datetime.now().timestamp())
                data_file_path = (
                    data_dir / f"{now_timestamp.replace('.', '_')}.{output}"
                )
                self.log.debug(f"Saving results to {data_file_path}")

                parsed_schema = parse_schema({})

                len_data = 0
                for i, pt in enumerate(partitions):
                    self.log.debug(f"Retrieving rows from partition {i}")
                    data = [dict(row) for row in pt]
                    del pt

                    len_data += len(data)

                    self.log.debug(f"Saving partition {i}")
                    if i == 0:
                        with open(data_file_path, "wb") as f:
                            writer(f, parsed_schema, data)
                    else:
                        with open(data_file_path, "a+b") as f:
                            writer(f, parsed_schema, data)
                    del data

                self.log.info(f"Retrieved {len_data} rows")

        if output == "json":
            return json.dumps(obj=output_data, cls=CustomJSONEncoder)
        else:
            return output_data


class MSSQLEngine(SqlAlchemyEngine):
    def __init__(self, dialect, driver, logger, mssql_driver, **kwargs):
        super().__init__(
            dialect, driver, logger, query={"driver": mssql_driver}, **kwargs
        )


class OracleEngine(SqlAlchemyEngine):
    def __init__(
        self,
        dialect,
        driver,
        logger,
        version,
        prefetchrows=oracledb.defaults.prefetchrows,
        **kwargs,
    ):
        oracledb.version = version
        oracledb.defaults.prefetchrows = prefetchrows
        super().__init__(dialect, driver, logger, **kwargs)


SQLALCHEMY_ENGINE_CONFIG = {
    "dialect": Field(StringSource),
    "driver": Field(StringSource),
    "username": Field(StringSource, is_required=False),
    "password": Field(StringSource, is_required=False),
    "host": Field(StringSource, is_required=False),
    "port": Field(IntSource, is_required=False),
    "database": Field(StringSource, is_required=False),
    "connect_args": Field(Permissive(), is_required=False),
}


@resource(
    config_schema=merge_dicts(
        SQLALCHEMY_ENGINE_CONFIG,
        {"mssql_driver": Field(StringSource, is_required=True)},
    )
)
def mssql(context):
    return MSSQLEngine(logger=context.log, **context.resource_config)


@resource(
    config_schema=merge_dicts(
        SQLALCHEMY_ENGINE_CONFIG,
        {
            "version": Field(StringSource, is_required=True),
            "prefetchrows": Field(IntSource, is_required=False),
            "arraysize": Field(IntSource, is_required=False),
        },
    )
)
def oracle(context):
    return OracleEngine(logger=context.log, **context.resource_config)
