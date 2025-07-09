from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetCheckSpec,
    AssetExecutionContext,
    Output,
    StaticPartitionsDefinition,
    asset,
)
from dagster_gcp import BigQueryResource

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf._google.directory.schema import (
    GROUPS_SCHEMA,
    MEMBERS_SCHEMA,
    ORGUNITS_SCHEMA,
    ROLE_ASSIGNMENTS_SCHEMA,
    ROLES_SCHEMA,
    USERS_SCHEMA,
)
from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.google.directory.resources import GoogleDirectoryResource

key_prefix = [CODE_LOCATION, "google", "directory"]


@asset(
    key=[*key_prefix, "orgunits"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "orgunits"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    kinds={"python"},
)
def orgunits(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_orgunits(org_unit_type="all")

    yield Output(value=([data], ORGUNITS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=[data], schema=ORGUNITS_SCHEMA
    )


@asset(
    key=[*key_prefix, "users"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "users"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    kinds={"python"},
)
def users(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_users(projection="full")

    yield Output(value=(data, USERS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=USERS_SCHEMA
    )


@asset(
    key=[*key_prefix, "groups"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "groups"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    kinds={"python"},
)
def groups(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_groups()

    yield Output(value=(data, GROUPS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=GROUPS_SCHEMA
    )


@asset(
    key=[*key_prefix, "roles"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "roles"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    kinds={"python"},
)
def roles(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_roles()

    yield Output(value=(data, ROLES_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=ROLES_SCHEMA
    )


@asset(
    key=[*key_prefix, "role_assignments"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "role_assignments"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    kinds={"python"},
)
def role_assignments(
    context: AssetExecutionContext, google_directory: GoogleDirectoryResource
):
    data = google_directory.list_role_assignments()

    yield Output(
        value=(data, ROLE_ASSIGNMENTS_SCHEMA), metadata={"record_count": len(data)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=ROLE_ASSIGNMENTS_SCHEMA
    )


@asset(
    key=[*key_prefix, "members"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "members"])],
    partitions_def=StaticPartitionsDefinition(
        [
            "group-students-camden@teamstudents.org",
            "group-students-miami@teamstudents.org",
            "group-students-newark@teamstudents.org",
        ]
    ),
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    kinds={"python"},
)
def members(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_members(group_key=context.partition_key)

    yield Output(value=(data, MEMBERS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=MEMBERS_SCHEMA
    )


@asset(
    key=[*key_prefix, "role_assignments_create"],
    check_specs=[
        AssetCheckSpec(
            name="zero_api_errors", asset=[*key_prefix, "role_assignments_create"]
        )
    ],
    group_name="google_directory",
    kinds={"python"},
)
def google_directory_role_assignments_create(
    context: AssetExecutionContext,
    db_bigquery: BigQueryResource,
    google_directory: GoogleDirectoryResource,
):
    query = "select * from kipptaf_extracts.rpt_google_directory__admin_import"
    errors = []

    context.log.info(msg=query)
    with db_bigquery.get_client() as bq:
        query_job = bq.query(query=query, project=db_bigquery.project)

    arrow = query_job.to_arrow()

    context.log.info(msg=f"Retrieved {arrow.num_rows} rows")

    if arrow.num_rows > 0:
        role_assignments_data = arrow.to_pylist()

        errors = google_directory.batch_insert_role_assignments(
            role_assignments=role_assignments_data
        )

        for e in errors:
            context.log.error(msg=e)

    yield Output(value=None)
    yield AssetCheckResult(
        passed=(len(errors) == 0),
        asset_key=context.asset_key,
        check_name="zero_api_errors",
        metadata={"errors": errors},
        severity=AssetCheckSeverity.WARN,
    )


@asset(
    key=[*key_prefix, "user_create"],
    check_specs=[
        AssetCheckSpec(name="zero_api_errors", asset=[*key_prefix, "user_create"])
    ],
    group_name="google_directory",
    kinds={"python"},
)
def google_directory_user_create(
    context: AssetExecutionContext,
    db_bigquery: BigQueryResource,
    google_directory: GoogleDirectoryResource,
):
    query = """
        select * from kipptaf_extracts.rpt_google_directory__users_import
        where is_create
    """
    errors = []

    context.log.info(msg=query)
    with db_bigquery.get_client() as bq:
        query_job = bq.query(query=query, project=db_bigquery.project)

    arrow = query_job.to_arrow()

    context.log.info(msg=f"Retrieved {arrow.num_rows} rows")

    if arrow.num_rows > 0:
        create_users = arrow.to_pylist()

        create_errors = google_directory.batch_insert_users(create_users)

        for ce in create_errors:
            context.log.error(msg=ce)
            errors.append(ce)

        members_data = [
            {
                "groupKey": u["groupKey"],
                "email": u["primaryEmail"],
                "delivery_settings": "DISABLED",
            }
            for u in create_users
        ]

        members_errors = google_directory.batch_insert_members(members_data)

        for me in members_errors:
            context.log.error(msg=me)
            errors.append(me)

    yield Output(value=None)
    yield AssetCheckResult(
        passed=(len(errors) == 0),
        asset_key=context.asset_key,
        check_name="zero_api_errors",
        metadata={"errors": errors},
        severity=AssetCheckSeverity.WARN,
    )


@asset(
    key=[*key_prefix, "user_update"],
    check_specs=[
        AssetCheckSpec(name="zero_api_errors", asset=[*key_prefix, "user_update"])
    ],
    group_name="google_directory",
    kinds={"python"},
)
def google_directory_user_update(
    context: AssetExecutionContext,
    db_bigquery: BigQueryResource,
    google_directory: GoogleDirectoryResource,
):
    query = """
        select * from kipptaf_extracts.rpt_google_directory__users_import
        where is_update
    """
    errors = []

    context.log.info(msg=query)
    with db_bigquery.get_client() as bq:
        query_job = bq.query(query=query, project=db_bigquery.project)

    arrow = query_job.to_arrow()

    context.log.info(msg=f"Retrieved {arrow.num_rows} rows")

    if arrow.num_rows > 0:
        update_users = arrow.to_pylist()

        errors = google_directory.batch_update_users(update_users)

        for e in errors:
            context.log.error(msg=e)

    yield Output(value=None)
    yield AssetCheckResult(
        passed=(len(errors) == 0),
        asset_key=context.asset_key,
        check_name="zero_api_errors",
        metadata={"errors": errors},
        severity=AssetCheckSeverity.WARN,
    )


google_directory_nonpartitioned_assets = [
    groups,
    orgunits,
    role_assignments,
    roles,
    users,
]

google_directory_partitioned_assets = [
    members,
]

assets = [
    *google_directory_nonpartitioned_assets,
    *google_directory_partitioned_assets,
    google_directory_role_assignments_create,
    google_directory_user_create,
    google_directory_user_update,
]
