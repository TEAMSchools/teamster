import pathlib

import fastavro
import oracledb
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from pydantic import PrivateAttr
from sqlalchemy import Select, TextClause

from teamster.libraries.powerschool.sis.schema import ORACLE_AVRO_SCHEMA_TYPES


class PowerSchoolODBCResource(ConfigurableResource):
    user: str
    password: str
    host: str
    port: str = "1521"
    service_name: str
    expire_time: int = 0
    retry_count: int = 0
    retry_delay: int = 1
    tcp_connect_timeout: float = 20.0

    _connect_params: oracledb.ConnectParams = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        # trunk-ignore(pyright/reportAttributeAccessIssue)
        oracledb.defaults.fetch_lobs = False

        self._log = _check.not_none(value=context.log)

        self._connect_params = oracledb.ConnectParams(
            user=self.user,
            password=self.password,
            host=self.host,
            port=int(self.port),
            service_name=self.service_name,
            expire_time=self.expire_time,
            retry_count=self.retry_count,
            retry_delay=self.retry_delay,
            tcp_connect_timeout=self.tcp_connect_timeout,
        )

    def connect(self):
        return oracledb.connect(params=self._connect_params)

    def execute_query(
        self,
        query: Select | TextClause,
        output_format: str | None = None,
        batch_size: int = 1000,
        prefetch_rows: int = oracledb.defaults.prefetchrows,
        array_size: int = oracledb.defaults.arraysize,
    ):
        self._log.debug("Opening connection to database")
        connection = self.connect()

        self._log.debug(f"Opening cursor on {connection.service_name}")
        cursor = connection.cursor()

        cursor.prefetchrows = prefetch_rows
        cursor.arraysize = array_size

        self._log.info(f"Executing query:\n{query}")
        cursor.execute(statement=str(query))

        if output_format == "avro":
            columns = []
            fields = []

            if isinstance(query, Select):
                record_name = query.get_final_froms()[0].description
            elif isinstance(query, TextClause):
                record_name = query.description

            for name, type, _, _, _, _, _ in cursor.description:
                columns.append(name.lower())
                fields.append(
                    {
                        "name": name.lower(),
                        "type": ["null", *ORACLE_AVRO_SCHEMA_TYPES.get(type.name, [])],
                        "default": None,
                    }
                )

            cursor.rowfactory = lambda *args: dict(zip(columns, args))

            output = self.result_to_avro(
                cursor=cursor,
                batch_size=batch_size,
                schema=fastavro.parse_schema(
                    schema={"type": "record", "name": record_name, "fields": fields}
                ),
            )
        else:
            return [row for row in cursor.fetchall()]

        self._log.debug("Closing cursor on connection")
        cursor.close()

        self._log.debug("Closing connection to database")
        connection.close()

        return output

    def result_to_avro(
        self,
        cursor: oracledb.Cursor,
        batch_size: int,
        schema,
        data_filepath: pathlib.Path | None = None,
    ):
        if data_filepath is None:
            data_filepath = pathlib.Path("env/data.avro").absolute()

        data_filepath.parent.mkdir(parents=True, exist_ok=True)

        with data_filepath.open("wb") as fo:
            fastavro.writer(
                fo=fo,
                schema=schema,
                records=[],
                codec="snappy",
                strict_allow_default=True,
            )

        len_rows = 0
        fo = data_filepath.open("a+b")

        self._log.info(f"Saving results to {data_filepath}")
        while True:
            rows = cursor.fetchmany(size=batch_size)

            if not rows:
                break

            fastavro.writer(
                fo=fo,
                schema=schema,
                records=rows,
                codec="snappy",
                strict_allow_default=True,
            )

            len_rows += len(rows)

            self._log.info(f"Saved {len_rows} rows")

        fo.close()

        return data_filepath
