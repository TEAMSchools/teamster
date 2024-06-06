import pathlib

from dagster import (
    AssetExecutionContext,
    AssetKey,
    AssetsDefinition,
    AssetSpec,
    DailyPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    _check,
    asset,
    config_from_files,
)
from slugify import slugify

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.tableau.schema import WORKBOOK_SCHEMA
from teamster.libraries.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.core.definitions.external_asset import (
    external_assets_from_specs,
)
from teamster.libraries.tableau.resources import TableauServerResource

config = config_from_files([f"{pathlib.Path(__file__).parent}/config/assets.yaml"])

workbook_asset_def = config["workbook"]["asset_def"]

asset_name = workbook_asset_def["name"]

asset_key = [*workbook_asset_def["key_prefix"], asset_name]


@asset(
    partitions_def=MultiPartitionsDefinition(
        {
            "workbook_id": StaticPartitionsDefinition(
                [a["metadata"]["id"] for a in config["external_assets"]]
            ),
            "date": DailyPartitionsDefinition(
                start_date=config["workbook"]["partitions_def"]["start_date"],
                end_offset=1,
            ),
        }
    ),
    check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    **workbook_asset_def,
)
def workbook(context: AssetExecutionContext, tableau: TableauServerResource):
    partition_key = _check.inst(context.partition_key, MultiPartitionKey)

    workbook = tableau._server.workbooks.get_by_id(
        partition_key.keys_by_dimension["workbook_id"]
    )

    tableau._server.workbooks.populate_views(workbook_item=workbook, usage=True)

    records = [
        {
            "content_url": workbook.content_url,
            "id": workbook.id,
            "name": workbook.name,
            "owner_id": workbook.owner_id,
            "project_id": workbook.project_id,
            "project_name": workbook.project_name,
            "size": workbook.size,
            "show_tabs": workbook.show_tabs,
            "webpage_url": workbook.webpage_url,
            "views": [
                {
                    "content_url": v.content_url,
                    "id": v.id,
                    "name": v.name,
                    "owner_id": v.owner_id,
                    "project_id": v.project_id,
                    "total_views": v.total_views,
                }
                for v in workbook.views
            ],
        }
    ]

    yield Output(value=(records, WORKBOOK_SCHEMA), metadata={"records": 1})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=records, schema=WORKBOOK_SCHEMA
    )


specs = [
    AssetSpec(
        key=AssetKey(
            [
                CODE_LOCATION,
                "tableau",
                slugify(text=a["name"], separator="_", regex_pattern=r"[^A-Za-z0-9_]"),
            ]
        ),
        description=a["name"],
        deps=a["deps"],
        metadata=a["metadata"],
        group_name="tableau",
    )
    for a in config["external_assets"]
]

external_assets: list[AssetsDefinition] = external_assets_from_specs(
    specs=specs, compute_kind="tableau"
)

assets = [
    workbook,
    *external_assets,
]
