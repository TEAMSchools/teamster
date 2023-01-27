import datetime
import json
import pathlib

import oracledb
from dagster import Field, IntSource, Permissive, StringSource, resource
from dagster._utils.merger import merge_dicts
from fastavro import parse_schema, writer
from sqlalchemy.engine import URL, create_engine

from teamster.core.utils.classes import CustomJSONEncoder

# https://cx-oracle.readthedocs.io/en/latest/user_guide/sql_execution.html#defaultfetchtypes
ORACLE_AVRO_SCHEMA_TYPES = {
    "DB_TYPE_BFILE": ["null"],
    "DB_TYPE_BINARY_DOUBLE": ["null", "double"],
    "DB_TYPE_BINARY_FLOAT": ["null", "float"],
    "DB_TYPE_BINARY_INTEGER": ["null", "int"],
    "DB_TYPE_BLOB": ["null", "bytes"],
    "DB_TYPE_BOOLEAN": ["null", "boolean"],
    "DB_TYPE_CHAR": ["null", "string"],
    "DB_TYPE_CLOB": ["null", "string"],
    "DB_TYPE_CURSOR": ["null"],
    "DB_TYPE_DATE": ["null", {"type": "int", "logicalType": "date"}],
    "DB_TYPE_INTERVAL_DS": [
        "null",
        {"type": "fixed", "name": "datetime.timedelta", "logicalType": "duration"},
    ],
    "DB_TYPE_INTERVAL_YM": ["null"],
    "DB_TYPE_JSON": ["null", {"type": "bytes", "logicalType": "json"}],
    "DB_TYPE_LONG": ["null", "string"],
    "DB_TYPE_LONG_RAW": ["null", "bytes"],
    "DB_TYPE_NCHAR": ["null", "string"],
    "DB_TYPE_NCLOB": ["null", "string"],
    "DB_TYPE_NUMBER": [
        "null",
        "int",
        "double",
        {"type": "bytes", "logicalType": "decimal", "precision": 40, "scale": 40},
    ],
    "DB_TYPE_NVARCHAR": ["null", "string"],
    "DB_TYPE_OBJECT": ["null"],
    "DB_TYPE_RAW": ["null", "bytes"],
    "DB_TYPE_ROWID": ["null", "string"],
    "DB_TYPE_TIMESTAMP": ["null", {"type": "long", "logicalType": "timestamp-micros"}],
    "DB_TYPE_TIMESTAMP_LTZ": [
        "null",
        {"type": "long", "logicalType": "timestamp-micros"},
    ],
    "DB_TYPE_TIMESTAMP_TZ": [
        "null",
        {"type": "long", "logicalType": "timestamp-micros"},
    ],
    "DB_TYPE_UROWID": ["null", "string"],
    "DB_TYPE_VARCHAR": ["null", "string"],
}


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

            result_cursor_descr = result.cursor.description
            if output in ["dict", "json"]:
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

                self.log.debug(f"Retrieved {len(output_data)} rows")
            elif output == "avro":
                data_dir = pathlib.Path("data").absolute()
                data_dir.mkdir(parents=True, exist_ok=True)

                now_timestamp = str(datetime.datetime.now().timestamp())
                output_data = data_dir / f"{now_timestamp.replace('.', '_')}.{output}"
                self.log.debug(f"Saving results to {output_data}")

                avro_schema_fields = []
                for col in result_cursor_descr:
                    avro_schema_fields.append(
                        {
                            "name": col[0].lower(),
                            "type": ORACLE_AVRO_SCHEMA_TYPES.get(
                                col[1].name, ["null"]
                            ),  # TODO: refactor based on db type
                        }
                    )
                self.log.debug(avro_schema_fields)

                avro_schema = parse_schema(
                    {
                        "type": "record",
                        "name": query.get_final_froms()[0].name,
                        "fields": avro_schema_fields,
                    }
                )

                len_data = 0
                for i, pt in enumerate(partitions):
                    self.log.debug(f"Retrieving rows from partition {i}")
                    data = [dict(row) for row in pt]
                    del pt

                    len_data += len(data)

                    self.log.debug(f"Saving partition {i}")
                    if i == 0:
                        with open(output_data, "wb") as f:
                            writer(
                                fo=f, schema=avro_schema, records=data, codec="snappy"
                            )
                    else:
                        with open(output_data, "a+b") as f:
                            writer(
                                fo=f, schema=avro_schema, records=data, codec="snappy"
                            )
                    del data

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
