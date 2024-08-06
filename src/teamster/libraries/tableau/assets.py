from dagster import (
    AssetExecutionContext,
    DailyPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    _check,
    asset,
)

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.tableau.resources import TableauServerResource


def build_tableau_workbook_stats_asset(
    code_location: str, workbook_ids: list[str], partition_start_date: str, schema
):
    asset_key = [code_location, "tableau", "workbook"]

    @asset(
        key=asset_key,
        partitions_def=MultiPartitionsDefinition(
            {
                "workbook_id": StaticPartitionsDefinition(workbook_ids),
                "date": DailyPartitionsDefinition(
                    start_date=partition_start_date, end_offset=1
                ),
            }
        ),
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
        io_manager_key="io_manager_gcs_avro",
        compute_kind="tableau",
        group_name="tableau",
    )
    def _asset(context: AssetExecutionContext, tableau: TableauServerResource):
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

        yield Output(value=(records, schema), metadata={"records": 1})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset
