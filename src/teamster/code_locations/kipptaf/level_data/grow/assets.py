import pathlib

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetCheckSpec,
    AssetExecutionContext,
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    asset,
    config_from_files,
)
from dagster_gcp import BigQueryResource

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.level_data.grow.schema import (
    ASSET_SCHEMA,
    ASSIGNMENT_SCHEMA,
    OBSERVATION_SCHEMA,
)
from teamster.libraries.level_data.grow.assets import build_grow_asset
from teamster.libraries.level_data.grow.resources import GrowResource

STATIC_PARTITONS_DEF = StaticPartitionsDefinition(["t", "f"])
MULTI_PARTITIONS_DEF = MultiPartitionsDefinition(
    {
        "archived": STATIC_PARTITONS_DEF,
        "last_modified": DailyPartitionsDefinition(
            start_date="2023-07-31", timezone=str(LOCAL_TIMEZONE), end_offset=1
        ),
    }
)

key_prefix = [CODE_LOCATION, "schoolmint", "grow"]
config_dir = pathlib.Path(__file__).parent / "config"

grow_static_partition_assets = [
    build_grow_asset(
        asset_key=[*key_prefix, e["asset_name"].replace("-", "_").replace("/", "_")],
        endpoint=e["asset_name"],
        partitions_def=STATIC_PARTITONS_DEF,
        schema=ASSET_SCHEMA[e["asset_name"]],
        op_tags=e.get("op_tags"),
    )
    for e in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

assignments = build_grow_asset(
    asset_key=[*key_prefix, "assignments"],
    endpoint="assignments",
    partitions_def=MULTI_PARTITIONS_DEF,
    schema=ASSIGNMENT_SCHEMA,
)

observations = build_grow_asset(
    asset_key=[*key_prefix, "observations"],
    endpoint="observations",
    partitions_def=MULTI_PARTITIONS_DEF,
    schema=OBSERVATION_SCHEMA,
)


@asset(
    key=[*key_prefix, "user_sync"],
    check_specs=[
        AssetCheckSpec(name="zero_api_errors", asset=[*key_prefix, "user_sync"])
    ],
    group_name="grow",
    kinds={"python"},
)
def grow_user_sync(
    context: AssetExecutionContext, db_bigquery: BigQueryResource, grow: GrowResource
):
    """
    query data
    """
    query = "select * from kipptaf_extracts.rpt_schoolmint_grow__users"
    errors = []

    context.log.info(msg=query)
    with db_bigquery.get_client() as bq:
        query_job = bq.query(query=query, project=db_bigquery.project)

    arrow = query_job.to_arrow()

    context.log.info(msg=f"Retrieved {arrow.num_rows} rows")
    users = arrow.to_pylist()

    """
    create/update users
    """
    for u in users:
        if u["surrogate_key_source"] == u["surrogate_key_destination"]:
            continue

        method = None
        request_args = ["users"]

        user_id = u["user_id"]
        inactive = u["inactive"]
        user_email = u["user_email"]

        # restore
        if inactive == 0 and u["archived_at"] is not None:
            try:
                context.log.info(f"RESTORING\t{user_email}")
                method = "PUT"
                request_args.extend([user_id, "restore"])

                grow.put(*request_args, params={"district": grow.district_id})

                # reset vars for update
                request_args = ["users"]
            except Exception as e:
                exception_details = {
                    "user_email": user_email,
                    "request_args": request_args,
                    "method": method,
                    "exception": e,
                }

                context.log.error(exception_details)
                errors.append(exception_details)

                continue

        # build user payload
        payload = {
            "district": grow.district_id,
            "name": u["user_name"],
            "email": user_email,
            "internalId": u["user_internal_id"],
            "inactive": inactive,
            "defaultInformation": {
                "school": u["school_id"],
                "gradeLevel": u["grade_id"],
                "course": u["course_id"],
            },
            "coach": u["coach_id"],
            "roles": [u["role_id"]],
        }

        try:
            # create
            if inactive == 0 and user_id is None:
                context.log.info(f"CREATING\t{user_email}")
                method = "POST"

                create_response = grow.post(*request_args, json=payload)

                u["user_id"] = create_response["_id"]
            # update
            elif inactive == 0 and user_id is not None:
                context.log.info(f"UPDATING\t{user_email}")
                method = "PUT"
                request_args.append(user_id)

                grow.put(*request_args, json=payload)
            # archive
            elif inactive == 1 and user_id is not None and u["archived_at"] is None:
                context.log.info(f"ARCHIVING\t{user_email}")
                method = "DELETE"
                request_args.append(user_id)

                grow.delete(*request_args)
        except Exception as e:
            exception_details = {
                "user_email": user_email,
                "request_args": request_args,
                "method": method,
                "payload": payload,
                "exception": e,
            }

            context.log.error(exception_details)
            errors.append(exception_details)

            continue

    """
    update school observation groups
    """
    schools = grow.get("schools")["data"]

    for school in schools:
        school_id = school["_id"]

        context.log.info(f"UPDATING\t{school['name']}")

        payload: dict = {"district": grow.district_id}

        school_users = [
            u
            for u in users
            if u["school_id"] == school_id
            and u["user_id"] is not None
            and u["inactive"] == 0
        ]

        # observation groups
        teachers_observation_group = [
            g for g in school["observationGroups"] if g["name"] == "Teachers"
        ][0]

        observees = [
            u["user_id"] for u in school_users if "observees" in u["group_type"]
        ]
        observers = set(
            [u["user_id"] for u in school_users if "observers" in u["group_type"]]
        )
        coaches = set(
            [u["coach_id"] for u in school_users if u["coach_id"] is not None]
        )

        payload["observationGroups"] = [
            {
                "_id": teachers_observation_group["_id"],
                "name": "Teachers",
                "observees": observees,
                "observers": list(observers | coaches),
            }
        ]

        # school admins
        admin_roles = {
            "admins": "School Admin",
            "assistantAdmins": "School Assistant Admin",
        }

        for key, role_name in admin_roles.items():
            payload[key] = [
                {"_id": u["user_id"], "name": u["user_name"]}
                for u in school_users
                if role_name == u["role_name"]
            ]

        grow.put("schools", school_id, json=payload)

    yield Output(value=None)
    yield AssetCheckResult(
        passed=(len(errors) == 0),
        asset_key=context.asset_key,
        check_name="zero_api_errors",
        metadata={"errors": errors},
        severity=AssetCheckSeverity.WARN,
    )


grow_multi_partitions_assets = [
    assignments,
    observations,
]

assets = [
    *grow_multi_partitions_assets,
    *grow_static_partition_assets,
    grow_user_sync,
]
