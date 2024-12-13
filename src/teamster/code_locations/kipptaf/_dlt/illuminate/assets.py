import json
import pathlib
from datetime import date

import yaml
from dagster import AssetExecutionContext, AssetKey, EnvVar, _check
from dagster_embedded_elt.dlt import DagsterDltResource, DagsterDltTranslator
from dlt import pipeline
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.sources.sql_database import remove_nullability_adapter, sql_database
from sqlalchemy.sql import Select, TableClause

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf._dlt.asset_decorator import dlt_assets


class CustomDagsterDltTranslator(DagsterDltTranslator):
    def __init__(self, code_location: str):
        self.code_location = code_location
        return super().__init__()

    def get_asset_key(self, resource):
        return AssetKey(
            [
                self.code_location,
                "dlt",
                resource.source_name,
                resource.explicit_args["schema"],
                resource.explicit_args["table"],
            ]
        )

    def get_deps_asset_keys(self, resource):
        return []

    def get_tags(self, resource):
        return {
            "dagster/concurrency_key": (
                f"dlt_{resource.source_name}_{self.code_location}"
            )
        }

    def get_kinds(self, resource, destination):
        return {"dlt", "postgresql", destination.destination_name}


def build_dlt_assets(
    code_location: str,
    credentials,
    schema: str,
    table_name: str,
    pipeline_name: str,
    destination: str,
    op_tags: dict[str, object] | None = None,
    filter_date_taken: bool = False,
):
    if op_tags is None:
        op_tags = {}

    op_tags.update(
        {
            "dagster/concurrency_key": f"dlt_{pipeline_name}_{code_location}",
            "dagster-k8s/config": {
                "container_config": {
                    "resources": {
                        "requests": {"cpu": "250m"},
                        "limits": {"cpu": "1250m"},
                    }
                }
            },
        },
    )

    def filter_date_taken_callback(query: Select, table: TableClause):
        return query.where(table.c.date_taken <= date(year=9999, month=12, day=31))

    if filter_date_taken:
        query_adapter_callback = filter_date_taken_callback
    else:
        query_adapter_callback = None

    # trunk-ignore(pyright/reportArgumentType)
    dlt_source = sql_database.with_args(name=pipeline_name)(
        credentials=credentials,
        schema=schema,
        table_names=[table_name],
        defer_table_reflect=True,
        table_adapter_callback=remove_nullability_adapter,
        query_adapter_callback=query_adapter_callback,
        chunk_size=500000,
    ).parallelize()

    @dlt_assets(
        dlt_source=dlt_source,
        dlt_pipeline=pipeline(
            pipeline_name=pipeline_name,
            destination=destination,
            dataset_name=f"dagster_{code_location}_dlt_{pipeline_name}_{schema}",
            progress="log",
        ),
        name=f"{code_location}__dlt__{pipeline_name}__{schema}__{table_name}",
        group_name=pipeline_name,
        dagster_dlt_translator=CustomDagsterDltTranslator(code_location),
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


config_file = pathlib.Path(__file__).parent / "config" / "illuminate.yaml"

assets = [
    build_dlt_assets(
        code_location=CODE_LOCATION,
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
        pipeline_name="illuminate",
        destination="bigquery",
        schema=a["schema"],
        **t,
    )
    for a in yaml.safe_load(config_file.read_text())["assets"]
    for t in a["tables"]
]
