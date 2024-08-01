import gc
import pathlib
from typing import Iterator, Sequence

import fastavro
import oracledb
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from pydantic import PrivateAttr
from sqlalchemy.engine import URL, Engine, Row, create_engine, result

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

    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = _check.not_none(value=context.log)

    def result_to_tuple_list(self, partitions) -> list[tuple]:
        self._log.debug("Retrieving rows from all partitions")
        pt_rows = [rows for pt in partitions for rows in pt]

        self._log.debug("Unpacking partition rows")
        output_data = [row for row in pt_rows]

        del pt_rows
        gc.collect()

        self._log.info(f"Retrieved {len(output_data)} rows")
        return output_data

    def result_to_dict_list(self, partitions):
        self._log.debug("Retrieving rows from all partitions")
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
        data_filepath: pathlib.Path | None = None,
    ):
        if data_filepath is None:
            data_filepath = pathlib.Path("env/data.avro").absolute()

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
            self._log.debug(f"Saving partition {i}")
            data = [row._mapping for row in pt]

            del pt
            gc.collect()

            len_data += len(data)

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


class OracleResource(SqlAlchemyEngineResource):
    version: str
    expire_time: int = 1
    retry_count: int = 0
    retry_delay: int = 1
    tcp_connect_timeout: float = 20.0

    _engine: Engine = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        oracledb.version = self.version

        self._engine = create_engine(
            url=URL.create(
                drivername=f"{self.dialect}+{self.driver}",
                username=self.username,
                password=self.password,
                host=self.host,
                port=int(self.port),
                database=self.database,
                query=self.query,
            ),
            connect_args={
                "expire_time": self.expire_time,
                "retry_count": self.retry_count,
                "retry_delay": self.retry_delay,
                "tcp_connect_timeout": self.tcp_connect_timeout,
            },
        )

        return super().setup_for_execution(context)

    def execute_query(
        self,
        query,
        output_format: str | None = None,
        partition_size: int | None = None,
        prefetch_rows: int = oracledb.defaults.prefetchrows,
        array_size: int = oracledb.defaults.arraysize,
    ):
        self._log.debug("Opening connection to engine")
        with self._engine.connect() as conn:
            self._log.info(f"Executing query:\n{query}")
            cursor_result = conn.execute(statement=query)

            if output_format == "avro":
                cursor = _check.not_none(value=cursor_result.cursor)

                # trunk-ignore(pyright/reportAttributeAccessIssue)
                cursor.prefetchrows = prefetch_rows
                cursor.arraysize = array_size

                schema = fastavro.parse_schema(
                    schema={
                        "type": "record",
                        "name": query.get_final_froms()[0].name,
                        "fields": [
                            {
                                "name": col.name.lower(),
                                "type": [
                                    "null",
                                    *ORACLE_AVRO_SCHEMA_TYPES.get(col.type.name, []),
                                ],
                                "default": None,
                            }
                            for col in cursor.description
                            if isinstance(col, oracledb.FetchInfo)
                        ],
                    }
                )

                output = self.result_to_avro(
                    partitions=cursor_result.partitions(partition_size), schema=schema
                )
            else:
                output = self.result_to_tuple_list(
                    partitions=cursor_result.partitions(partition_size)
                )

        return output
