import copy
import gc
import json
import pathlib
import sys

import oracledb
from dagster import ConfigurableResource
from dagster._core.execution.context.init import InitResourceContext
from fastavro import parse_schema, writer
from pydantic import PrivateAttr
from sqlalchemy.engine import URL, Engine, create_engine

from teamster.core.utils.classes import CustomJSONEncoder

from .schema import ORACLE_AVRO_SCHEMA_TYPES

sys.modules["cx_Oracle"] = oracledb


class SqlAlchemyEngineResource(ConfigurableResource):
    dialect: str
    driver: str
    username: str = None
    password: str = None
    host: str = None
    port: int = None
    database: str = None
    query: dict = None

    _engine: Engine = PrivateAttr()

    def execute_query(self, query, partition_size, output, connect_kwargs={}):
        context = self.get_resource_context()

        context.log.debug("Opening connection to engine")
        with self._engine.connect(**connect_kwargs) as conn:
            context.log.info(f"Executing query:\n{query}")
            result = conn.execute(statement=query)

            if output in ["dict", "json", "avro"]:
                context.log.debug("Staging result mappings")
                result = result.mappings()

            output_data = self.parse_result(
                output_format=output,
                partitions=result.partitions(size=partition_size),
                table_name=query.get_final_froms()[0].name,
                columns=result.cursor.description,
            )

        if output == "json":
            return json.dumps(obj=output_data, cls=CustomJSONEncoder)
        else:
            return output_data

    def parse_result(self, output_format, partitions, table_name=None, columns=None):
        context = self.get_resource_context()

        if output_format in ["dict", "json"] or output_format is None:
            context.log.debug("Retrieving rows from all partitions")
            pt_rows = [rows for pt in partitions for rows in pt]

            context.log.debug("Unpacking partition rows")
            output_data = [
                dict(row) if output_format in ["dict", "json"] else row
                for row in pt_rows
            ]

            del pt_rows
            gc.collect()

            context.log.debug(f"Retrieved {len(output_data)} rows")
        elif output_format == "avro":
            data_dir = pathlib.Path("data").absolute()

            data_dir.mkdir(parents=True, exist_ok=True)
            output_data = data_dir / f"{table_name}.{output_format}"
            context.log.debug(f"Saving results to {output_data}")

            avro_schema_fields = []
            for col in columns:
                # TODO: refactor based on db type
                col_type = copy.deepcopy(ORACLE_AVRO_SCHEMA_TYPES.get(col[1].name, []))
                col_type.insert(0, "null")

                avro_schema_fields.append(
                    {"name": col[0].lower(), "type": col_type, "default": None}
                )
            context.log.debug(avro_schema_fields)

            avro_schema = parse_schema(
                {"type": "record", "name": table_name, "fields": avro_schema_fields}
            )

            len_data = 0
            for i, pt in enumerate(partitions):
                context.log.debug(f"Retrieving rows from partition {i}")
                data = [dict(row) for row in pt]

                del pt
                gc.collect()

                len_data += len(data)

                context.log.debug(f"Saving partition {i}")
                if i == 0:
                    with output_data.open("wb") as f:
                        writer(fo=f, schema=avro_schema, records=data, codec="snappy")
                else:
                    with output_data.open("a+b") as f:
                        writer(fo=f, schema=avro_schema, records=data, codec="snappy")

                del data
                gc.collect()

            context.log.debug(f"Retrieved {len_data} rows")

        return output_data


class MSSQLResource(ConfigurableResource):
    engine: SqlAlchemyEngineResource
    driver: str

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self.engine._engine = create_engine(
            url=URL.create(
                drivername=f"{self.engine.dialect}+{self.engine.driver}",
                username=self.engine.username,
                password=self.engine.password,
                host=self.engine.host,
                port=self.engine.port,
                database=self.engine.database,
                query={"driver": self.driver},
            )
        )

        return super().setup_for_execution(context)


class OracleResource(ConfigurableResource):
    engine: SqlAlchemyEngineResource
    version: str
    prefetchrows: int = oracledb.defaults.prefetchrows
    arraysize: int = oracledb.defaults.arraysize

    def setup_for_execution(self, context: InitResourceContext) -> None:
        oracledb.version = self.version
        oracledb.defaults.prefetchrows = self.prefetchrows

        self.engine._engine = create_engine(
            url=URL.create(
                drivername=f"{self.engine.dialect}+{self.engine.driver}",
                username=self.engine.username,
                password=self.engine.password,
                host=self.engine.host,
                port=self.engine.port,
                database=self.engine.database,
                query=self.engine.query,
            ),
            arraysize=self.arraysize,
        )
