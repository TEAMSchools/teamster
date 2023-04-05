import copy
import gc
import json
import pathlib
import sys

import oracledb
from dagster import Field, IntSource, Permissive, StringSource, resource
from dagster._utils.merger import merge_dicts
from fastavro import parse_schema, writer
from sqlalchemy.engine import URL, create_engine

from teamster.core.utils.classes import CustomJSONEncoder

sys.modules["cx_Oracle"] = oracledb

# https://cx-oracle.readthedocs.io/en/latest/user_guide/sql_execution.html#defaultfetchtypes
ORACLE_AVRO_SCHEMA_TYPES = {
    "DB_TYPE_BINARY_DOUBLE": ["double"],
    "DB_TYPE_BINARY_FLOAT": ["float"],
    "DB_TYPE_BINARY_INTEGER": ["int"],
    "DB_TYPE_BLOB": ["bytes"],
    "DB_TYPE_BOOLEAN": ["boolean"],
    "DB_TYPE_CHAR": ["string"],
    "DB_TYPE_CLOB": ["string"],
    "DB_TYPE_DATE": [{"type": "int", "logicalType": "date"}],
    "DB_TYPE_INTERVAL_DS": [
        {"type": "fixed", "name": "datetime.timedelta", "logicalType": "duration"},
    ],
    "DB_TYPE_JSON": [{"type": "bytes", "logicalType": "json"}],
    "DB_TYPE_LONG": ["string"],
    "DB_TYPE_LONG_RAW": ["bytes"],
    "DB_TYPE_LONG_NVARCHAR": ["string"],
    "DB_TYPE_NCHAR": ["string"],
    "DB_TYPE_NCLOB": ["string"],
    "DB_TYPE_NUMBER": [
        "int",
        "double",
        {"type": "bytes", "logicalType": "decimal", "precision": 40, "scale": 40},
    ],
    "DB_TYPE_NVARCHAR": ["string"],
    "DB_TYPE_RAW": ["bytes"],
    "DB_TYPE_ROWID": ["string"],
    "DB_TYPE_TIMESTAMP": [{"type": "long", "logicalType": "timestamp-micros"}],
    "DB_TYPE_TIMESTAMP_LTZ": [{"type": "long", "logicalType": "timestamp-micros"}],
    "DB_TYPE_TIMESTAMP_TZ": [{"type": "long", "logicalType": "timestamp-micros"}],
    "DB_TYPE_UROWID": ["string"],
    "DB_TYPE_VARCHAR": ["string"],
    # "DB_TYPE_BFILE": [],
    # "DB_TYPE_CURSOR": [],
    # "DB_TYPE_INTERVAL_YM": [],
    # "DB_TYPE_OBJECT": [],
}


class SqlAlchemyEngine(object):
    def __init__(self, dialect, driver, logger, **kwargs):
        self.log = logger

        engine_keys = ["arraysize", "connect_args"]
        url_kwargs = {k: v for k, v in kwargs.items() if k not in engine_keys}
        engine_kwargs = {k: v for k, v in kwargs.items() if k in engine_keys}

        self.connection_url = URL.create(drivername=f"{dialect}+{driver}", **url_kwargs)
        self.engine = create_engine(url=self.connection_url, **engine_kwargs)

    def execute_query(self, query, partition_size, output, connect_kwargs={}):
        # TODO: add file_format param, refactor output logic
        self.log.debug("Opening connection to engine")
        with self.engine.connect(**connect_kwargs) as conn:
            self.log.info(f"Executing query:\n{query}")
            result = conn.execute(statement=query)

            result_cursor_descr = result.cursor.description
            if output in ["dict", "json", "avro"]:
                self.log.debug("Staging result mappings")
                result = result.mappings()
            else:
                pass

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
                gc.collect()

                self.log.debug(f"Retrieved {len(output_data)} rows")
            elif output == "avro":
                table_name = query.get_final_froms()[0].name

                data_dir = pathlib.Path("data").absolute()

                data_dir.mkdir(parents=True, exist_ok=True)
                output_data = data_dir / f"{table_name}.{output}"
                self.log.debug(f"Saving results to {output_data}")

                avro_schema_fields = []
                for col in result_cursor_descr:
                    # TODO: refactor based on db type
                    col_type = copy.deepcopy(
                        ORACLE_AVRO_SCHEMA_TYPES.get(col[1].name, [])
                    )
                    col_type.insert(0, "null")

                    avro_schema_fields.append(
                        {"name": col[0].lower(), "type": col_type, "default": None}
                    )
                self.log.debug(avro_schema_fields)

                avro_schema = parse_schema(
                    {
                        "type": "record",
                        "name": table_name,
                        "fields": avro_schema_fields,
                    }
                )

                len_data = 0
                for i, pt in enumerate(partitions):
                    self.log.debug(f"Retrieving rows from partition {i}")
                    data = [dict(row) for row in pt]

                    del pt
                    gc.collect()

                    len_data += len(data)

                    self.log.debug(f"Saving partition {i}")
                    if i == 0:
                        with output_data.open("wb") as f:
                            writer(
                                fo=f, schema=avro_schema, records=data, codec="snappy"
                            )
                    else:
                        with output_data.open("a+b") as f:
                            writer(
                                fo=f, schema=avro_schema, records=data, codec="snappy"
                            )

                    del data
                    gc.collect()

                self.log.debug(f"Retrieved {len_data} rows")

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
    "dialect": Field(config=StringSource),
    "driver": Field(config=StringSource),
    "username": Field(config=StringSource, is_required=False),
    "password": Field(config=StringSource, is_required=False),
    "host": Field(config=StringSource, is_required=False),
    "port": Field(config=IntSource, is_required=False),
    "database": Field(config=StringSource, is_required=False),
    "connect_args": Field(config=Permissive(), is_required=False),
}


@resource(
    config_schema=merge_dicts(
        SQLALCHEMY_ENGINE_CONFIG,
        {"mssql_driver": Field(config=StringSource, is_required=True)},
    )
)
def mssql(context):
    return MSSQLEngine(logger=context.log, **context.resource_config)


@resource(
    config_schema=merge_dicts(
        SQLALCHEMY_ENGINE_CONFIG,
        {
            "version": Field(config=StringSource, is_required=True),
            "prefetchrows": Field(config=IntSource, is_required=False),
            "arraysize": Field(config=IntSource, is_required=False),
        },
    )
)
def oracle(context):
    return OracleEngine(logger=context.log, **context.resource_config)
