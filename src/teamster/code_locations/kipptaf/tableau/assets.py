import pathlib

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetCheckSpec,
    AssetExecutionContext,
    AssetsDefinition,
    Output,
    asset,
    config_from_files,
)
from dagster_gcp import BigQueryResource

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.tableau.schema import VIEW_COUNT_PER_VIEW_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_folder_asset
from teamster.libraries.tableau.assets import build_tableau_workbook_refresh_asset
from teamster.libraries.tableau.resources import TableauServerResource

workbook_refresh_assets: list[AssetsDefinition] = [
    build_tableau_workbook_refresh_asset(code_location=CODE_LOCATION, **a)
    for a in config_from_files([f"{pathlib.Path(__file__).parent}/config/assets.yaml"])[
        "assets"
    ]
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
    key=[CODE_LOCATION, "tableau", "teacher_gradebook_email_group_update"],
    check_specs=[
        AssetCheckSpec(
            name="zero_api_errors",
            asset=[CODE_LOCATION, "tableau", "teacher_gradebook_email_group_update"],
        )
    ],
    group_name="tableau",
    kinds={"python"},
)
def teacher_gradebook_email_group_update(
    context: AssetExecutionContext,
    db_bigquery: BigQueryResource,
    tableau: TableauServerResource,
):
    """
    query data
    """
    errors = []
    query = """
        select distinct region, teacher_tableau_username,
        from kipptaf_tableau.rpt_tableau__gradebook_audit
        where teacher_tableau_username is not null
        order by region asc, teacher_tableau_username asc
    """

    context.log.info(msg=query)
    with db_bigquery.get_client() as bq:
        query_job = bq.query(query=query, project=db_bigquery.project)

    arrow = query_job.to_arrow()

    context.log.info(msg=f"Retrieved {arrow.num_rows} rows")
    query_users = arrow.to_pylist()

    """
    get matching Tableau users
    """
    tableau_users = tableau.get_all(endpoint=tableau._server.users, pagesize=1000)

    for qu in query_users:
        tableau_user_match = [
            tu.id
            for tu in tableau_users
            if tu.name.lower() == qu["teacher_tableau_username"]
        ]

        if tableau_user_match:
            qu["id"] = tableau_user_match[0]
        else:
            warning_message = (
                f"User {qu['teacher_tableau_username']} not found on Tableau"
            )

            context.log.warning(msg=warning_message)
            errors.append(warning_message)

    """
    sync group membership
    """

    yield Output(value=None)
    yield AssetCheckResult(
        passed=(len(errors) == 0),
        asset_key=context.asset_key,
        check_name="zero_api_errors",
        metadata={"errors": errors},
        severity=AssetCheckSeverity.WARN,
    )


assets = [
    view_count_per_view,
    *workbook_refresh_assets,
]
