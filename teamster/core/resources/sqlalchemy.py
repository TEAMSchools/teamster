import gzip
import json
import pathlib
import sys
import uuid

import oracledb
from dagster import Field, IntSource, StringSource, resource
from dagster._utils import merge_dicts
from sqlalchemy.engine import URL, create_engine

from teamster.core.utils import CustomJSONEncoder

sys.modules["cx_Oracle"] = oracledb  # patched until sqlalchemy supports oracledb (v2)

PARTITION_SIZE = 10000


class SqlAlchemyEngine(object):
    def __init__(self, dialect, driver, logger, **kwargs):
        engine_keys = ["arraysize"]
        engine_kwargs = {k: v for k, v in kwargs.items() if k in engine_keys}
        url_kwargs = {k: v for k, v in kwargs.items() if k not in engine_keys}

        self.log = logger
        self.connection_url = URL.create(drivername=f"{dialect}+{driver}", **url_kwargs)
        self.engine = create_engine(url=self.connection_url, **engine_kwargs)

    def execute_query(self, query, output_fmt="dict"):
        self.log.info(f"Executing query:\n{query}")

        with self.engine.connect() as conn:
            result = conn.execute(statement=query)
            if output_fmt in ["dict", "json", "files"]:
                result_stg = result.mappings()
            else:
                result_stg = result

            partitions = result_stg.partitions(size=PARTITION_SIZE)
            if output_fmt == "files":
                tmp_dir = pathlib.Path(uuid.uuid4().hex).absolute()
                tmp_dir.mkdir(parents=True, exist_ok=True)

                len_data = 0
                output_obj = []
                for i, pt in enumerate(partitions):
                    self.log.debug(f"Querying partition {i}")
                    data = [dict(row) for row in pt]
                    len_data += len(data)

                    del pt

                    tmp_file = tmp_dir / (uuid.uuid4().hex + ".json.gz")
                    self.log.debug(f"Saving to {tmp_file}")
                    with gzip.open(tmp_file, "wb") as gz:
                        gz.write(
                            json.dumps(obj=data, cls=CustomJSONEncoder).encode("utf-8")
                        )

                    del data

                    output_obj.append(tmp_file)
                self.log.info(f"Retrieved {len_data} rows.")
            else:
                pts_unpacked = [rows for pt in partitions for rows in pt]
                output_obj = [dict(row) for row in pts_unpacked]
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
