from dagster import AssetExecutionContext, AssetKey, AssetsDefinition, Output, asset
from dagster_gcp import BigQueryResource
from tableauserverclient import Pager

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf._dbt.assets import manifest
from teamster.code_locations.kipptaf.tableau.schema import VIEW_COUNT_PER_VIEW_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_folder_asset
from teamster.libraries.tableau.assets import build_tableau_workbook_refresh_asset
from teamster.libraries.tableau.resources import TableauServerResource

workbook_refresh_assets: list[AssetsDefinition] = [
    build_tableau_workbook_refresh_asset(code_location=CODE_LOCATION, **exposure)
    for exposure in manifest["exposures"].values()
    if "tableau" in exposure["config"]["meta"]["dagster"].get("kinds", [])
]

view_count_per_view = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "tableau", "view_count_per_view"],
    remote_dir_regex=r"/data-team/kipptaf/tableau/view_count_per_view",
    remote_file_regex=r".+\.csv",
    file_sep="\t",
    file_encoding="utf-16",
    avro_schema=VIEW_COUNT_PER_VIEW_SCHEMA,
    ssh_resource_key="ssh_couchdrop",
)


@asset(
    key=[CODE_LOCATION, "tableau", "teacher_gradebook_group_sync"],
    deps=[
        AssetKey(
            ["kipptaf", "tableau", "int_tableau__gradebook_audit_teacher_scaffold"]
        )
    ],
    group_name="tableau",
    kinds={"python", "task"},
)
def tableau_teacher_gradebook_group_sync(
    context: AssetExecutionContext,
    db_bigquery: BigQueryResource,
    tableau: TableauServerResource,
):
    # query source data
    query = """
      select
        concat('Teacher Gradebook Email - Auto - ', region) as group_name,
        array_agg(distinct teacher_tableau_username) as user_names,
      from kipptaf_tableau.int_tableau__gradebook_audit_teacher_scaffold
      where teacher_tableau_username is not null
      group by region
    """

    context.log.info(msg=query)
    with db_bigquery.get_client() as bq:
        query_job = bq.query(query=query, project=db_bigquery.project)

    arrow = query_job.to_arrow()

    context.log.info(msg=f"Retrieved {arrow.num_rows} rows")
    query_results = arrow.to_pylist()

    # update groups
    for result in query_results:
        group_item = [
            group
            for group in Pager(endpoint=tableau._server.groups)
            if group.name == result["group_name"]
        ][0]

        tableau._server.groups.populate_users(group_item=group_item)
        existing_users = [user.id for user in group_item.users]

        if existing_users:
            tableau._server.groups.remove_users(
                group_item=group_item, users=existing_users
            )

        tableau._server.groups.add_users(
            group_item=group_item,
            users=[
                user
                for user in Pager(endpoint=tableau._server.users)
                if user.name in result["user_names"]
            ],
        )

    yield Output(value=None)


assets = [
    *workbook_refresh_assets,
    tableau_teacher_gradebook_group_sync,
    view_count_per_view,
]
