from dagster import (
    AssetExecutionContext,
    AutoMaterializePolicy,
    AutoMaterializeRule,
    DailyPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    _check,
    asset,
)
from slugify import slugify

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.tableau.resources import TableauServerResource


def build_tableau_workbook_refresh_asset(
    code_location: str,
    name: str,
    deps: list[str],
    metadata: dict[str, str],
    cron_schedule: str | list[str] | None = None,
    timezone: str | None = None,
):
    if cron_schedule is None:
        auto_materialize_policy = None
    elif isinstance(cron_schedule, str):
        auto_materialize_policy = AutoMaterializePolicy(
            rules={
                AutoMaterializeRule.materialize_on_cron(
                    cron_schedule=cron_schedule,
                    timezone=_check.not_none(value=timezone),
                )
            }
        )
    else:
        auto_materialize_policy = AutoMaterializePolicy(
            rules={
                AutoMaterializeRule.materialize_on_cron(
                    cron_schedule=cs,
                    timezone=_check.not_none(value=timezone),
                )
                for cs in cron_schedule
            }
        )

    @asset(
        key=[
            code_location,
            "tableau",
            slugify(text=name, separator="_", regex_pattern=r"[^A-Za-z0-9_]"),
        ],
        description=name,
        deps=deps,
        metadata=metadata,
        auto_materialize_policy=auto_materialize_policy,
        compute_kind="tableau",
        group_name="tableau",
        output_required=False,
    )
    def _asset(context: AssetExecutionContext, tableau: TableauServerResource):
        workbook = tableau._server.workbooks.get_by_id(
            context.assets_def.metadata_by_key[context.asset_key]["id"]
        )

        tableau._server.workbooks.refresh(workbook)

        return None

    return _asset


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
