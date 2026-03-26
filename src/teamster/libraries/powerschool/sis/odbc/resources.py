"""Dagster resource for PowerSchool SIS Oracle ODBC connections.

Provides a ConfigurableResource that wraps oracledb to connect to the
PowerSchool Oracle database, execute queries, and stream results to Avro
block files. Requires an active SSH tunnel opened separately via
SSHResource.open_ssh_tunnel() before connect() is called.
"""

import pathlib

import fastavro
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from oracledb import Connection, ConnectParams, Cursor, connect, defaults
from pydantic import PrivateAttr
from sqlalchemy import Select, TextClause

from teamster.libraries.powerschool.sis.odbc.schema import ORACLE_AVRO_SCHEMA_TYPES


class PowerSchoolODBCResource(ConfigurableResource):
    """Dagster resource for connecting to the PowerSchool SIS Oracle database.

    Wraps oracledb to open cursors, execute SQL queries, and write results
    to Avro block files using the column-type mapping in schema.py. Requires
    an active SSH tunnel before connect() is called.

    Attributes:
        user: Oracle database username.
        password: Oracle database password.
        host: Hostname or IP of the Oracle listener (tunnel local endpoint).
        port: Oracle listener port. Defaults to "1521".
        service_name: Oracle service name identifying the target database.
        expire_time: keepalive interval in minutes (0 = disabled).
        retry_count: Number of connection retries on failure.
        retry_delay: Seconds between connection retries.
        tcp_connect_timeout: Seconds before a TCP connection attempt times out.
    """

    user: str
    password: str
    host: str
    port: str = "1521"
    service_name: str
    expire_time: int = 0
    retry_count: int = 0
    retry_delay: int = 1
    tcp_connect_timeout: float = 20.0

    _connect_params: ConnectParams = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        """Initialise the resource before the first op/asset execution.

        Disables LOB streaming (fetch_lobs = False so CLOBs/BLOBs are returned
        as plain Python strings/bytes), stores the Dagster log manager, and
        builds the ConnectParams object that connect() will use.

        Args:
            context: Dagster resource initialisation context providing the log
                manager.
        """
        defaults.fetch_lobs = False

        self._log = check.not_none(value=context.log)

        self._connect_params = ConnectParams(
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
        """Open and return an Oracle database connection.

        Uses the ConnectParams built during setup_for_execution(). An active
        SSH tunnel to the database host must already be established before
        calling this method.

        Returns:
            An open oracledb Connection object.
        """
        self._log.debug("Opening connection to database")
        return connect(params=self._connect_params)

    def execute_query(
        self,
        connection: Connection,
        query: Select | TextClause,
        output_format: str | None = None,
        batch_size: int = 1000,
        prefetch_rows: int = defaults.prefetchrows,
        array_size: int = defaults.arraysize,
    ):
        """Execute a SQL query and return results in the requested format.

        Opens a cursor on the given connection, applies prefetch/array-size
        tuning, and executes the query. Returns either a list of tuples
        (default) or an Avro file path (when output_format="avro").

        Args:
            connection: An open oracledb Connection returned by connect().
            query: A SQLAlchemy Select or TextClause whose string representation
                is passed to cursor.execute().
            output_format: When set to "avro", results are streamed to an Avro
                block file via result_to_avro() and the file path is returned.
                Any other value (including None) returns a list of tuples.
            batch_size: Number of rows fetched per batch when writing Avro output.
            prefetch_rows: oracledb cursor prefetchrows tuning parameter.
            array_size: oracledb cursor arraysize tuning parameter.

        Returns:
            A list of tuples when output_format is not "avro", or a
            pathlib.Path pointing to the written Avro file otherwise.
        """
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

            # trunk-ignore-begin(pyright): oracledb lacks type stubs; cursor.description elements are FetchInfo at runtime
            for col_info in cursor.description or []:
                col_name = col_info[0].lower()
                col_type_name = col_info[1].name

                columns.append(col_name)
                fields.append(
                    {
                        "name": col_name,
                        "type": [
                            "null",
                            *ORACLE_AVRO_SCHEMA_TYPES.get(col_type_name, []),
                        ],
                        "default": None,
                    }
                )
            # trunk-ignore-end(pyright)

            cursor.rowfactory = lambda *args: dict(zip(columns, args, strict=False))

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

        return output

    def result_to_avro(
        self,
        cursor: Cursor,
        batch_size: int,
        schema,
        data_filepath: pathlib.Path | None = None,
    ):
        """Stream cursor rows into a Snappy-compressed Avro block file.

        Writes an empty Avro container with the given schema first, then
        appends batches of rows fetched from the cursor until the result set
        is exhausted. The cursor's rowfactory must produce dicts (keyed by
        lowercase column name) before this method is called.

        Args:
            cursor: An executed oracledb Cursor whose rowfactory returns dicts.
            batch_size: Number of rows fetched per fastavro.writer() call.
            schema: A parsed fastavro schema (from fastavro.parse_schema()).
            data_filepath: Destination path for the Avro file. Defaults to
                env/data.avro relative to the current working directory.

        Returns:
            A pathlib.Path pointing to the written Avro file.
        """
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
