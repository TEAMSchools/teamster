import json
import pathlib

import yaml
from dagster import AssetExecutionContext, AssetKey, EnvVar, _check
from dagster_embedded_elt.dlt import (
    DagsterDltResource,
    DagsterDltTranslator,
    dlt_assets,
)
from dlt import pipeline
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.sources.sql_database import sql_database

from teamster.code_locations.kipptaf import CODE_LOCATION


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
        if resource.is_transformer:
            pipe = resource._pipe

            while pipe.has_parent:
                pipe = pipe.parent

            return [AssetKey(f"{resource.source_name}_{pipe.name}")]

        return [
            AssetKey(
                [
                    self.code_location,
                    resource.source_name,
                    resource.explicit_args["schema"],
                    resource.explicit_args["table"],
                ]
            )
        ]


def build_dlt_assets(
    credentials,
    schema: str,
    table_names: list[str],
    pipeline_name: str,
    destination: str,
):
    @dlt_assets(
        name=f"dlt__{pipeline_name}__{schema}",
        dlt_source=sql_database(
            credentials=credentials,
            schema=schema,
            table_names=table_names,
            defer_table_reflect=True,
        ),
        dlt_pipeline=pipeline(
            pipeline_name=pipeline_name,
            destination=destination,
            dataset_name=f"dagster_dlt_{pipeline_name}_{schema}",
            progress="log",
        ),
        dagster_dlt_translator=CustomDagsterDltTranslator(CODE_LOCATION),
    )
    def _assets(context: AssetExecutionContext, dlt: DagsterDltResource):
        yield from dlt.run(
            context=context,
            credentials=json.load(
                fp=open(file="/etc/secret-volume/gcloud_teamster_dlt_keyfile.json")
            ),
        )

    return _assets


illuminate_credentials = ConnectionStringCredentials(
    {
        "drivername": _check.not_none(
            value=EnvVar("ILLUMINATE_DB_DRIVERNAME").get_value()
        ),
        "database": EnvVar("ILLUMINATE_DB_DATABASE").get_value(),
        "password": EnvVar("ILLUMINATE_DB_PASSWORD").get_value(),
        "username": EnvVar("ILLUMINATE_DB_USERNAME").get_value(),
        "host": EnvVar("ILLUMINATE_DB_HOST").get_value(),
    }
)

config_file = pathlib.Path(__file__).parent / "config" / "illuminate.yaml"

assets = [
    build_dlt_assets(
        credentials=illuminate_credentials,
        pipeline_name="illuminate",
        destination="bigquery",
        **a,
    )
    for a in yaml.safe_load(config_file.read_text())["assets"]
]
