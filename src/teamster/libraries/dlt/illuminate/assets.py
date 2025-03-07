from datetime import date

from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt import pipeline
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.common.runtime.collector import LogCollector
from dlt.destinations import bigquery
from dlt.sources.sql_database import remove_nullability_adapter, sql_database
from sqlalchemy.sql import Select, TableClause


class IlluminateDagsterDltTranslator(DagsterDltTranslator):
    def __init__(self, code_location: str):
        self.code_location = code_location
        return super().__init__()

    def get_asset_spec(self, data):
        asset_spec = super().get_asset_spec(data)

        asset_spec = asset_spec.replace_attributes(
            key=[
                self.code_location,
                "dlt",
                "illuminate",
                data.resource.explicit_args["schema"],
                data.resource.explicit_args["table"],
            ],
            deps=[],
        )

        asset_spec = asset_spec.merge_attributes(kinds={"postgresql"})

        return asset_spec


def filter_date_taken_callback(query: Select, table: TableClause):
    """date_taken is a postgres infinity date type, breaks psycopg"""
    return query.where(table.c.date_taken <= date(year=9999, month=12, day=31))


def build_illuminate_dlt_assets(
    sql_database_credentials: ConnectionStringCredentials,
    dlt_credentials: dict,
    code_location: str,
    schema: str,
    table_name: str,
    filter_date_taken: bool = False,
    op_tags: dict[str, object] | None = None,
):
    if op_tags is None:
        op_tags = {}

    dlt_source = sql_database.with_args(name="illuminate", parallelized=True)(
        credentials=sql_database_credentials,
        schema=schema,
        table_names=[table_name],
        defer_table_reflect=True,
        backend="pyarrow",
        table_adapter_callback=remove_nullability_adapter,
        query_adapter_callback=(
            filter_date_taken_callback if filter_date_taken else None
        ),
    )

    dlt_pipeline = pipeline(
        pipeline_name="illuminate",
        destination=bigquery(autodetect_schema=True),
        dataset_name=f"dagster_{code_location}_dlt_illuminate_{schema}",
        progress=LogCollector(dump_system_stats=False),
    )

    @dlt_assets(
        dlt_source=dlt_source,
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__dlt__illuminate__{schema}__{table_name}",
        dagster_dlt_translator=IlluminateDagsterDltTranslator(code_location),
        group_name="illuminate",
        pool=f"dlt_illuminate_{code_location}",
        op_tags=op_tags,
    )
    def _assets(context: AssetExecutionContext, dlt: DagsterDltResource):
        yield from dlt.run(
            context=context, credentials=dlt_credentials, write_disposition="replace"
        )

    return _assets
