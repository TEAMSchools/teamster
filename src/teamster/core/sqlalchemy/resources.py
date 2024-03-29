import gc
import json
import pathlib
from typing import Iterator, Sequence

import oracledb
from dagster import ConfigurableResource, InitResourceContext
from fastavro import parse_schema, writer
from pydantic import PrivateAttr
from sqlalchemy.engine import URL, Engine, Row, create_engine, result

from teamster.core.utils.classes import CustomJSONEncoder

from .schema import ORACLE_AVRO_SCHEMA_TYPES


class SqlAlchemyEngineResource(ConfigurableResource):
    dialect: str
    driver: str | None = None
    username: str | None = None
    password: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    query: dict = {}

    _engine: Engine = PrivateAttr()

    def execute_query(
        self,
        query,
        partition_size,
        connect_kwargs: dict | None = None,
        output_format=None,
        data_filepath="env/data.avro",
        call_timeout=0,
    ):
        if connect_kwargs is None:
            connect_kwargs = {}

        context = self.get_resource_context()

        context.log.info("Opening connection to engine")
        with self._engine.connect(**connect_kwargs) as conn:
            conn.call_timeout = call_timeout  # type: ignore

            context.log.info(f"Executing query:\n{query}")
            cursor_result = conn.execute(statement=query)

            if output_format in ["dict", "json"]:
                context.log.info("Retrieving rows from all partitions")

                cursor_result = cursor_result.mappings()

                output = self.result_to_dict_list(
                    partitions=cursor_result.partitions(size=partition_size)
                )

                if output_format == "json":
                    output = json.dumps(obj=output, cls=CustomJSONEncoder)

                context.log.info(f"Retrieved {len(output)} rows")
            elif output_format == "avro":
                avro_schema = parse_schema(
                    {
                        "type": "record",
                        "name": query.get_final_froms()[0].name,
                        "fields": [
                            {
                                "name": col[0].lower(),
                                "type": [
                                    "null",
                                    *ORACLE_AVRO_SCHEMA_TYPES.get(col[1].name, []),  # type: ignore
                                ],
                                "default": None,
                            }
                            for col in cursor_result.cursor.description
                        ],
                    }
                )

                output = self.result_to_avro(
                    partitions=cursor_result.partitions(size=partition_size),
                    schema=avro_schema,
                    data_filepath=pathlib.Path(data_filepath).absolute(),
                )
            else:
                context.log.info("Retrieving rows from all partitions")

                output = self.result_to_tuple_list(
                    partitions=cursor_result.partitions(size=partition_size)
                )

                context.log.info(f"Retrieved {len(output)} rows")

        return output

    def result_to_tuple_list(self, partitions):
        context = self.get_resource_context()

        pt_rows = [rows for pt in partitions for rows in pt]

        context.log.debug("Unpacking partition rows")
        output_data = [row for row in pt_rows]

        del pt_rows
        gc.collect()

        return output_data

    def result_to_dict_list(self, partitions):
        context = self.get_resource_context()

        pt_rows = [rows for pt in partitions for rows in pt]

        context.log.debug("Unpacking partition rows")
        output_data = [dict(row) for row in pt_rows]

        del pt_rows
        gc.collect()

        return output_data

    def result_to_avro(
        self,
        partitions: Iterator[Sequence[Row[result._TP]]],
        schema,
        data_filepath: pathlib.Path,
    ):
        context = self.get_resource_context()

        context.log.info(f"Saving results to {data_filepath}")
        data_filepath.parent.mkdir(parents=True, exist_ok=True)

        with data_filepath.open("wb") as fo:
            writer(
                fo=fo,
                schema=schema,
                records=[],
                codec="snappy",
                strict_allow_default=True,
            )

        len_data = 0
        fo = data_filepath.open("a+b")

        for i, pt in enumerate(partitions):
            context.log.debug(f"Retrieving rows from partition {i}")

            data = [row._mapping for row in pt]
            del pt
            gc.collect()

            len_data += len(data)

            context.log.debug(f"Saving partition {i}")
            writer(
                fo=fo,
                schema=schema,
                records=data,
                codec="snappy",
                strict_allow_default=True,
            )

            del data
            gc.collect()

        fo.close()

        return data_filepath


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
