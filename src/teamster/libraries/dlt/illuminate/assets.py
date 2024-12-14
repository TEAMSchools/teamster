import json
import os
from datetime import date

from dagster import AssetExecutionContext, AssetKey, EnvVar, _check
from dagster_embedded_elt.dlt import DagsterDltResource, DagsterDltTranslator
from dlt import pipeline
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.common.runtime.collector import LogCollector
from dlt.sources.sql_database import remove_nullability_adapter, sql_database
from sqlalchemy.sql import Select, TableClause

from teamster.libraries.dlt.asset_decorator import dlt_assets


class IlluminateDagsterDltTranslator(DagsterDltTranslator):
    def __init__(self, code_location: str):
        self.code_location = code_location
        return super().__init__()

    def get_asset_key(self, resource):
        return AssetKey(
            [
                self.code_location,
                "dlt",
                "illuminate",
                resource.explicit_args["schema"],
                resource.explicit_args["table"],
            ]
        )

    def get_deps_asset_keys(self, resource):
        return []

    def get_kinds(self, resource, destination):
        return {"dlt", "postgresql", destination.destination_name}


def filter_date_taken_callback(query: Select, table: TableClause):
    """date_taken is a postgres infinity date type, breaks psycopg"""
    return query.where(table.c.date_taken <= date(year=9999, month=12, day=31))


def build_illuminate_dlt_assets(
    code_location: str,
    schema: str,
    table_name: str,
    filter_date_taken: bool = False,
    op_tags: dict[str, object] | None = None,
):
    if op_tags is None:
        op_tags = {}

    op_tags.update({"dagster/concurrency_key": f"dlt_illuminate_{code_location}"})

    # trunk-ignore(pyright/reportArgumentType)
    dlt_source = sql_database.with_args(name="illuminate")(
        credentials=ConnectionStringCredentials(
            {
                "drivername": _check.not_none(
                    value=EnvVar("ILLUMINATE_DB_DRIVERNAME").get_value()
                ),
                "database": EnvVar("ILLUMINATE_DB_DATABASE").get_value(),
                "password": EnvVar("ILLUMINATE_DB_PASSWORD").get_value(),
                "username": EnvVar("ILLUMINATE_DB_USERNAME").get_value(),
                "host": EnvVar("ILLUMINATE_DB_HOST").get_value(),
            }
        ),
        schema=schema,
        table_names=[table_name],
        defer_table_reflect=True,
        backend="pyarrow",
        table_adapter_callback=remove_nullability_adapter,
        query_adapter_callback=(
            filter_date_taken_callback if filter_date_taken else None
        ),
    ).parallelize()

    # bigquery cannot load data type 'json' from 'parquet' files
    os.environ["DESTINATION__BIGQUERY__AUTODETECT_SCHEMA"] = "true"

    dlt_pipeline = pipeline(
        pipeline_name="illuminate",
        destination="bigquery",
        dataset_name=f"dagster_{code_location}_dlt_illuminate_{schema}",
        progress=LogCollector(dump_system_stats=False),
    )

    @dlt_assets(
        dlt_source=dlt_source,
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__dlt__illuminate__{schema}__{table_name}",
        group_name="illuminate",
        dagster_dlt_translator=IlluminateDagsterDltTranslator(code_location),
        op_tags=op_tags,
    )
    def _assets(context: AssetExecutionContext, dlt: DagsterDltResource):
        yield from dlt.run(
            context=context,
            credentials=json.load(
                fp=open(file="/etc/secret-volume/gcloud_teamster_dlt_keyfile.json")
            ),
        )

    return _assets
