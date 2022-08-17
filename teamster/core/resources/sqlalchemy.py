import json
import sys

import oracledb
from dagster import Field, IntSource, StringSource, resource
from dagster._utils import merge_dicts
from sqlalchemy import text
from sqlalchemy.engine import URL, create_engine

from teamster.core.utils import CustomJSONEncoder

sys.modules["cx_Oracle"] = oracledb  # patched until sqlalchemy supports oracledb (v2)


class SqlAlchemyEngine(object):
    def __init__(self, dialect, driver, logger, **kwargs):
        self.log = logger
        self.connection_url = URL.create(drivername=f"{dialect}+{driver}", **kwargs)
        self.engine = create_engine(url=self.connection_url)

    def execute_text_query(self, query, output="dict"):
        self.log.info(f"Executing query:\n{query}")

        with self.engine.connect() as conn:
            result = conn.execute(statement=text(query))

            if output in ["dict", "json"]:
                output_obj = [dict(row) for row in result.mappings()]
            else:
                output_obj = [row for row in result]

        self.log.info(f"Retrieved {len(output_obj)} rows.")
        if output == "json":
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
        },
    )
)
def oracle(context):
    return OracleEngine(logger=context.log, **context.resource_config)
