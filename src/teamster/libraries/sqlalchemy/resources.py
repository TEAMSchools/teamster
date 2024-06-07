import gc
import json
import pathlib
from typing import Iterator, Sequence

import fastavro
import oracledb
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from pydantic import PrivateAttr
from sqlalchemy.engine import URL, Engine, Row, create_engine, result

from teamster.libraries.core.utils.classes import CustomJSONEncoder
from teamster.libraries.sqlalchemy.schema import ORACLE_AVRO_SCHEMA_TYPES


class SqlAlchemyEngineResource(ConfigurableResource):
    dialect: str
    driver: str | None = None
    username: str | None = None
    password: str | None = None
    host: str | None = None
    port: str = ""
    database: str | None = None
    query: dict = {}

    _engine: Engine = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)

    def execute_query(
        self,
        query,
        partition_size,
        connect_kwargs: dict | None = None,
        output_format=None,
        data_filepath="env/data.avro",
    ):
        if connect_kwargs is None:
            connect_kwargs = {}

        data_filepath = pathlib.Path(data_filepath).absolute()

        self._log.info("Opening connection to engine")
        with self._engine.connect(**connect_kwargs) as conn:
            self._log.info(f"Executing query:\n{query}")
            cursor_result = conn.execute(statement=query)

            if output_format in ["dict", "json"]:
                cursor_result = cursor_result.mappings()

                output = self.result_to_dict_list(
                    cursor_result.partitions(partition_size)
                )
            elif output_format == "avro":
                fields = []
                schema = {"type": "record", "name": query.get_final_froms()[0].name}
                cursor = _check.not_none(value=cursor_result.cursor)

                for col in cursor.description:
                    col = _check.inst(col, oracledb.FetchInfo)

                    fields.append(
                        {
                            "name": col.name.lower(),
                            "type": [
                                "null",
                                *ORACLE_AVRO_SCHEMA_TYPES.get(col.type.name, []),
                            ],
                            "default": None,
                        }
                    )

                schema["fields"] = fields

                parsed_schema = fastavro.parse_schema(schema=schema)

                output = self.result_to_avro(
                    partitions=cursor_result.partitions(partition_size),
                    schema=parsed_schema,
                    data_filepath=data_filepath,
                )
            else:
                output = self.result_to_tuple_list(
                    partitions=cursor_result.partitions(partition_size)
                )

        if output_format == "json":
            output = json.dumps(obj=output, cls=CustomJSONEncoder)

        return output

    def result_to_tuple_list(self, partitions) -> list[tuple]:
        self._log.info("Retrieving rows from all partitions")
        pt_rows = [rows for pt in partitions for rows in pt]

        self._log.debug("Unpacking partition rows")
        output_data = [row for row in pt_rows]

        del pt_rows
        gc.collect()

        self._log.info(f"Retrieved {len(output_data)} rows")
        return output_data

    def result_to_dict_list(self, partitions):
        self._log.info("Retrieving rows from all partitions")
        pt_rows = [rows for pt in partitions for rows in pt]

        self._log.debug("Unpacking partition rows")
        output_data = [dict(row) for row in pt_rows]

        del pt_rows
        gc.collect()

        self._log.info(f"Retrieved {len(output_data)} rows")
        return output_data

    def result_to_avro(
        self,
        partitions: Iterator[Sequence[Row[result._TP]]],
        schema,
        data_filepath: pathlib.Path,
    ):
        self._log.info(f"Saving results to {data_filepath}")
        data_filepath.parent.mkdir(parents=True, exist_ok=True)

        with data_filepath.open("wb") as fo:
            fastavro.writer(
                fo=fo,
                schema=schema,
                records=[],
                codec="snappy",
                strict_allow_default=True,
            )

        len_data = 0
        fo = data_filepath.open("a+b")

        for i, pt in enumerate(partitions):
            self._log.debug(f"Retrieving rows from partition {i}")
            data = [row._mapping for row in pt]

            del pt
            gc.collect()

            len_data += len(data)

            self._log.debug(f"Saving partition {i}")
            fastavro.writer(
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
                port=int(self.engine.port),
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
                port=int(self.engine.port),
                database=self.engine.database,
                query=self.engine.query,
            ),
            arraysize=self.arraysize,
        )
