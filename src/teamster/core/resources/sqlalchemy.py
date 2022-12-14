import gzip
import json
import pathlib
import sys
from datetime import datetime

import oracledb
from dagster import Field, IntSource, Permissive, StringSource, resource
from dagster._utils import merge_dicts
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

    def execute_query(self, query, partition_size, output_fmt, connect_kwargs={}):
        self.log.debug("Opening connection to engine")
        with self.engine.connect(**connect_kwargs) as conn:
            self.log.info(f"Executing query:\n{query}")
            result = conn.execute(statement=query)

            if output_fmt in ["dict", "json", "file"]:
                self.log.debug("Staging result mappings")
                result_stg = result.mappings()
            else:
                result_stg = result

            self.log.debug("Partitioning results")
            partitions = result_stg.partitions(size=partition_size)

            if output_fmt == "file":
                tmp_dir = pathlib.Path("data").absolute()
                tmp_dir.mkdir(parents=True, exist_ok=True)

                len_data = 0
                output_obj = []
                for i, pt in enumerate(partitions):
                    self.log.debug(f"Retrieving rows from partition {i}")

                    now_ts = str(datetime.now().timestamp())
                    tmp_file_path = tmp_dir / f"{now_ts.replace('.', '_')}.json.gz"

                    data = [dict(row) for row in pt]
                    del pt

                    len_data += len(data)

                    self.log.debug(f"Saving data to {tmp_file_path}")
                    with gzip.open(tmp_file_path, "wb") as gz:
                        gz.write(
                            json.dumps(obj=data, cls=CustomJSONEncoder).encode("utf-8")
                        )
                    del data

                    output_obj.append(tmp_file_path)

                self.log.info(f"Retrieved {len_data} rows.")
            else:
                self.log.debug("Retrieving rows from all partitions")
                pt_rows = [rows for pt in partitions for rows in pt]

        if output_fmt != "file":
            self.log.debug("Unpacking partition rows")
            if output_fmt in ["dict", "json"]:
                output_obj = [dict(row) for row in pt_rows]
            else:
                output_obj = [row for row in pt_rows]
            del pt_rows

            self.log.info(f"Retrieved {len(output_obj)} rows.")

        if output_fmt == "json":
            return json.dumps(obj=output_obj, cls=CustomJSONEncoder)
        else:
            return output_obj


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
